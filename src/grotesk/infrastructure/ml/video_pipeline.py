import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

import torch
from diffusers import AutoencoderKLWan, LucyEditPipeline
from diffusers.utils import export_to_video, load_video

from grotesk.domain.processing.model import TimelineOperation
from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.types import VideoEditResult


class HuggingFaceVideoPipeline:
    def __init__(self, config: MLConfig) -> None:
        self._config = config
        self._pipeline: Any | None = None
        self._vae: Any | None = None

    def edit(
        self,
        source_path: Path,
        model_id: str,
        prompt_text: str | None,
        operations: list[TimelineOperation],
    ) -> VideoEditResult:
        with tempfile.TemporaryDirectory(prefix="grotesk-video-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            video_duration = self._probe_duration(source_path)
            effective_operations = self._build_effective_operations(video_duration, prompt_text, operations)
            segment_paths: list[Path] = []
            cursor = 0.0

            for index, operation in enumerate(effective_operations):
                operation_start = float(operation.start_second)
                operation_end = float(operation.end_second)
                if operation_start > cursor:
                    untouched_path = temp_dir / f"untouched-{index}.mp4"
                    self._extract_segment(source_path, untouched_path, cursor, operation_start)
                    segment_paths.append(untouched_path)

                input_segment_path = temp_dir / f"input-{index}.mp4"
                edited_segment_path = temp_dir / f"edited-{index}.mp4"
                self._extract_segment(source_path, input_segment_path, operation_start, operation_end)
                self._run_model(
                    input_segment_path,
                    edited_segment_path,
                    model_id=model_id,
                    prompt=self._compose_prompt(prompt_text, operation.prompt),
                )
                segment_paths.append(edited_segment_path)
                cursor = operation_end

            if cursor < video_duration:
                tail_path = temp_dir / "tail.mp4"
                self._extract_segment(source_path, tail_path, cursor, video_duration)
                segment_paths.append(tail_path)

            concatenated_path = temp_dir / "concatenated.mp4"
            self._concatenate(segment_paths, concatenated_path)

            final_path = temp_dir / "final.mp4"
            self._restore_audio(source_path, concatenated_path, final_path)
            handle = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            handle.close()
            staged_path = Path(handle.name)
            shutil.copy2(final_path, staged_path)
            return {
                "output_path": staged_path,
                "model_name": model_id,
                "operation_count": len(effective_operations),
                "width": self._config.video_width,
                "height": self._config.video_height,
                "fps": self._config.video_fps,
            }

    @staticmethod
    def _build_effective_operations(
        video_duration: float,
        prompt_text: str | None,
        operations: list[TimelineOperation],
    ) -> list[TimelineOperation]:
        if operations:
            sorted_operations = sorted(operations, key=lambda item: item.start_second)
            last_end = 0
            for operation in sorted_operations:
                if operation.start_second < last_end:
                    raise ValueError("Video editing operations must not overlap.")
                if operation.end_second > math.ceil(video_duration):
                    raise ValueError("Video editing operation exceeds source video duration.")
                last_end = operation.end_second
            return sorted_operations

        if not prompt_text or not prompt_text.strip():
            raise ValueError("Video editing requires prompt_text or at least one timeline operation.")

        duration_end = max(1, math.ceil(video_duration))
        return [TimelineOperation(start_second=0, end_second=duration_end, prompt=prompt_text.strip())]

    def _compose_prompt(self, prompt_text: str | None, operation_prompt: str) -> str:
        if prompt_text and prompt_text.strip():
            return f"{prompt_text.strip()}. {operation_prompt.strip()}".strip()
        return operation_prompt.strip()

    def _run_model(self, input_segment_path: Path, output_segment_path: Path, model_id: str, prompt: str) -> None:
        pipeline = self._get_pipeline(model_id)
        target_fps = self._config.video_fps
        segment_duration = max(self._probe_duration(input_segment_path), 1.0 / target_fps)
        num_frames = max(1, min(self._config.video_max_frames, math.ceil(segment_duration * target_fps)))

        def convert_video(video_frames: list[Any]) -> list[Any]:
            limited_frames = video_frames[:num_frames]
            return [frame.resize((self._config.video_width, self._config.video_height)) for frame in limited_frames]

        loaded_video = load_video(str(input_segment_path), convert_method=convert_video)
        output = pipeline(
            prompt=prompt,
            video=loaded_video,
            negative_prompt="",
            height=self._config.video_height,
            width=self._config.video_width,
            num_frames=num_frames,
            guidance_scale=self._config.video_guidance_scale,
        ).frames[0]
        export_to_video(output, str(output_segment_path), fps=target_fps)

    def _get_pipeline(self, model_id: str) -> Any:
        if self._pipeline is not None and getattr(self._pipeline, "model_id", None) == model_id:
            return self._pipeline

        use_cuda = self._config.device.startswith("cuda") and torch.cuda.is_available()
        torch_dtype = torch.bfloat16 if use_cuda else torch.float32
        vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=torch.float32)
        pipeline = LucyEditPipeline.from_pretrained(model_id, vae=vae, torch_dtype=torch_dtype)
        if use_cuda:
            pipeline.to(self._config.device)
        setattr(pipeline, "model_id", model_id)
        self._vae = vae
        self._pipeline = pipeline
        return pipeline

    def _extract_segment(self, source_path: Path, output_path: Path, start_second: float, end_second: float) -> None:
        duration = max(end_second - start_second, 0.05)
        self._run_command(
            [
                self._config.ffmpeg_binary,
                "-y",
                "-ss",
                f"{start_second:.3f}",
                "-i",
                str(source_path),
                "-t",
                f"{duration:.3f}",
                "-vf",
                f"scale={self._config.video_width}:{self._config.video_height},fps={self._config.video_fps}",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )

    def _concatenate(self, segment_paths: Iterable[Path], output_path: Path) -> None:
        concat_file = output_path.with_suffix(".txt")
        concat_file.write_text(
            "".join(f"file '{segment_path.as_posix()}'\n" for segment_path in segment_paths),
            encoding="utf-8",
        )
        self._run_command(
            [
                self._config.ffmpeg_binary,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )

    def _restore_audio(self, source_path: Path, video_path: Path, output_path: Path) -> None:
        self._run_command(
            [
                self._config.ffmpeg_binary,
                "-y",
                "-i",
                str(video_path),
                "-i",
                str(source_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a?",
                "-shortest",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                str(output_path),
            ]
        )

    def _probe_duration(self, source_path: Path) -> float:
        completed_process = subprocess.run(
            [
                self._config.ffprobe_binary,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(completed_process.stdout.strip())

    @staticmethod
    def _run_command(command: list[str]) -> None:
        completed_process = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed_process.returncode != 0:
            raise RuntimeError(completed_process.stderr.strip() or "ffmpeg command failed")
