import logging
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Iterable

import cv2
import ftfy
import torch
from diffusers import AutoencoderKLWan, LucyEditPipeline
from diffusers.pipelines.lucy import pipeline_lucy_edit as _lucy_pipeline_module
from diffusers.utils import export_to_video
from PIL import Image

from grotesk.domain.processing.model import TimelineOperation
from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.types import VideoEditResult

_lucy_pipeline_module.ftfy = ftfy

logger = logging.getLogger(__name__)


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
        *,
        video_config: MLConfig | None = None,
    ) -> VideoEditResult:
        vconf = video_config if video_config is not None else self._config
        with tempfile.TemporaryDirectory(prefix="grotesk-video-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            logger.info("edit: temp_dir=%s source=%s model_id=%s", temp_dir, source_path, model_id)
            video_duration = self._probe_duration(source_path)
            logger.info("edit: source_duration=%.3fs", video_duration)
            effective_operations = self._build_effective_operations(video_duration, prompt_text, operations)
            logger.info("edit: operations=%s", len(effective_operations))
            segment_paths: list[Path] = []
            cursor = 0.0

            for index, operation in enumerate(effective_operations):
                operation_start = float(operation.start_second)
                operation_end = float(operation.end_second)
                if operation_start > cursor:
                    untouched_path = temp_dir / f"untouched-{index}.mp4"
                    logger.info(
                        "segment %s: copy untouched [%.3fs .. %.3fs] -> %s",
                        index,
                        cursor,
                        operation_start,
                        untouched_path.name,
                    )
                    self._extract_segment(source_path, untouched_path, cursor, operation_start, vconf)
                    segment_paths.append(untouched_path)

                input_segment_path = temp_dir / f"input-{index}.mp4"
                edited_segment_path = temp_dir / f"edited-{index}.mp4"
                logger.info(
                    "segment %s: extract [%.3fs .. %.3fs] -> %s",
                    index,
                    operation_start,
                    operation_end,
                    input_segment_path.name,
                )
                self._extract_segment(source_path, input_segment_path, operation_start, operation_end, vconf)
                self._run_model(
                    input_segment_path,
                    edited_segment_path,
                    model_id=model_id,
                    prompt=self._compose_prompt(prompt_text, operation.prompt),
                    video_cfg=vconf,
                )
                segment_paths.append(edited_segment_path)
                cursor = operation_end

            if cursor < video_duration:
                tail_path = temp_dir / "tail.mp4"
                logger.info("tail: extract [%.3fs .. %.3fs] -> %s", cursor, video_duration, tail_path.name)
                self._extract_segment(source_path, tail_path, cursor, video_duration, vconf)
                segment_paths.append(tail_path)

            concatenated_path = temp_dir / "concatenated.mp4"
            logger.info("concatenate: %s segments -> %s", len(segment_paths), concatenated_path.name)
            self._concatenate(segment_paths, concatenated_path)

            final_path = temp_dir / "final.mp4"
            logger.info("mux audio: video=%s + source audio -> %s", concatenated_path.name, final_path.name)
            self._restore_audio(source_path, concatenated_path, final_path)
            handle = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            handle.close()
            staged_path = Path(handle.name)
            shutil.copy2(final_path, staged_path)
            logger.info("edit: done staged_output=%s", staged_path)
            return {
                "output_path": staged_path,
                "model_name": model_id,
                "operation_count": len(effective_operations),
                "width": vconf.video_width,
                "height": vconf.video_height,
                "fps": vconf.video_fps,
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

    @staticmethod
    def _largest_temporal_valid_at_most(max_frames: int, factor: int) -> int:
        """Наибольшее n ≤ max_frames с (n - 1) % factor == 0 (для Wan/Lucy temporal VAE)."""
        if max_frames < 1:
            return 1
        remainder = (max_frames - 1) % factor
        return max_frames - remainder

    def _load_video_pil_frames(
        self, input_segment_path: Path, num_frames: int, video_cfg: MLConfig
    ) -> list[Image.Image]:
        cap = cv2.VideoCapture(str(input_segment_path))
        if not cap.isOpened():
            msg = f"Failed to open video: {input_segment_path}"
            raise RuntimeError(msg)
        frames: list[Image.Image] = []
        try:
            while len(frames) < num_frames:
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    break
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                frames.append(Image.fromarray(rgb))
        finally:
            cap.release()
        if not frames:
            msg = f"No frames read from: {input_segment_path}"
            raise RuntimeError(msg)
        target_size = (video_cfg.video_width, video_cfg.video_height)
        resized = [frame.resize(target_size) for frame in frames[:num_frames]]
        logger.info("frames: read %s frames (requested %s) from %s", len(resized), num_frames, input_segment_path.name)
        return resized

    def _run_model(
        self,
        input_segment_path: Path,
        output_segment_path: Path,
        model_id: str,
        prompt: str,
        *,
        video_cfg: MLConfig,
    ) -> None:
        pipeline = self._get_pipeline(model_id)
        target_fps = video_cfg.video_fps
        segment_duration = max(self._probe_duration(input_segment_path), 1.0 / target_fps)
        num_frames = max(1, min(video_cfg.video_max_frames, math.ceil(segment_duration * target_fps)))
        temporal_align = int(os.environ.get("HF_VIDEO_TEMPORAL_ALIGN", "4"))
        if temporal_align > 0 and (num_frames - 1) % temporal_align != 0:
            # Нужно num_frames ≡ 1 (mod temporal_align), как в Lucy (см. vae_scale_factor_temporal).
            aligned = ((num_frames - 1 + temporal_align - 1) // temporal_align) * temporal_align + 1
            if aligned > video_cfg.video_max_frames:
                aligned = HuggingFaceVideoPipeline._largest_temporal_valid_at_most(
                    video_cfg.video_max_frames,
                    temporal_align,
                )
                logger.info(
                    "Lucy: выравнивание вверх превысило video_max_frames → берём %s",
                    aligned,
                )
            logger.info(
                "Lucy: num_frames %s -> %s для temporal VAE (выравнивание по %s)",
                num_frames,
                aligned,
                temporal_align,
            )
            num_frames = aligned
        num_inference_steps = video_cfg.video_num_inference_steps

        logger.info(
            "Lucy inference: segment=%s num_frames=%s fps=%s guidance=%s steps=%s device=%s",
            input_segment_path.name,
            num_frames,
            target_fps,
            video_cfg.video_guidance_scale,
            num_inference_steps,
            self._config.device,
        )
        logger.info(
            "Lucy: loading %s PIL frames (then T5 encode + latents; on CPU this is slow and quiet without logs)...",
            num_frames,
        )
        loaded_video = self._load_video_pil_frames(input_segment_path, num_frames, video_cfg)

        heartbeat_sec = float(os.environ.get("HF_VIDEO_PROGRESS_INTERVAL_SEC", "5"))
        pipeline_started = time.monotonic()
        # Этапы внутри LucyEditPipeline.__call__: (1) T5 encode_prompt (2) prepare_latents с VAE.encode по кадрам
        # (3) цикл денойза — здесь вызывается callback_on_step_end (4) VAE.decode без tqdm.
        logger.info(
            "Lucy: запуск pipeline — этапы: 1) текстовый энкодер T5  2) VAE encode условия (%s кадров, на CPU долго)  "
            "3) денойз (~%s итераций scheduler)  4) VAE decode результата. Колбэки только на этапе 3.",
            num_frames,
            num_inference_steps,
        )
        logger.info(
            "Lucy: пока нет строк «Lucy denoise» — идёт этап 1–2 (не зависание). Heartbeat каждые %.1fs.",
            heartbeat_sec,
        )

        progress: dict[str, Any] = {"stage": "prepare", "denoise_step": 0, "denoise_total": None}

        def _lucy_step_callback(
            pipe: Any,
            step_idx: int,
            timestep: int,
            callback_kwargs: dict[str, Any],
        ) -> dict[str, Any]:
            sched = getattr(pipe, "scheduler", None)
            total_steps = len(sched.timesteps) if sched is not None and hasattr(sched, "timesteps") else None
            progress["stage"] = "denoise"
            progress["denoise_step"] = step_idx + 1
            progress["denoise_total"] = total_steps
            remaining = (total_steps - step_idx - 1) if total_steps is not None else None
            logger.info(
                "Lucy denoise: шаг %s/%s (осталось итераций цикла: %s), timestep=%s",
                step_idx + 1,
                total_steps if total_steps is not None else "?",
                remaining if remaining is not None else "?",
                timestep,
            )
            if total_steps is not None and step_idx + 1 >= total_steps:
                progress["stage"] = "decode"
                logger.info(
                    "Lucy: денойз завершён → этап 4: VAE decode выходного видео (CPU, без tqdm; дальше heartbeat).",
                )
            return {}

        stop_heartbeat = threading.Event()

        def _heartbeat() -> None:
            while not stop_heartbeat.wait(heartbeat_sec):
                elapsed = time.monotonic() - pipeline_started
                stage = progress["stage"]
                if stage == "prepare":
                    logger.info(
                        "Lucy heartbeat: %.0fs — подготовка: T5 и VAE encode условия по кадрам. "
                        "Денойз ещё не начался.",
                        elapsed,
                    )
                elif stage == "denoise":
                    total = progress["denoise_total"]
                    cur = progress["denoise_step"]
                    left = (total - cur) if isinstance(total, int) else "?"
                    logger.info(
                        "Lucy heartbeat: %.0fs — денойз в процессе (последний залогированный шаг %s/%s, осталось ~%s).",
                        elapsed,
                        cur,
                        total if total is not None else "?",
                        left,
                    )
                else:
                    logger.info(
                        "Lucy heartbeat: %.0fs — VAE decode / постобработка выхода (это самый долгий участок на CPU).",
                        elapsed,
                    )

        hb = threading.Thread(target=_heartbeat, name="lucy-pipeline-heartbeat", daemon=True)
        hb.start()
        try:
            lucy_out = pipeline(
                prompt=prompt,
                video=loaded_video,
                negative_prompt="",
                height=video_cfg.video_height,
                width=video_cfg.video_width,
                num_frames=num_frames,
                num_inference_steps=num_inference_steps,
                guidance_scale=video_cfg.video_guidance_scale,
                callback_on_step_end=_lucy_step_callback,
                callback_on_step_end_tensor_inputs=["latents"],
            )
        finally:
            stop_heartbeat.set()

        logger.info("Lucy: pipeline.__call__ завершён (денойз + VAE decode). Экспорт кадров в mp4...")
        output = lucy_out.frames[0]
        frame_count = len(output) if hasattr(output, "__len__") else -1
        logger.info("Lucy: кадров для export_to_video: %s", frame_count)

        export_to_video(output, str(output_segment_path), fps=target_fps)

        if not output_segment_path.is_file():
            msg = f"export_to_video не создал файл: {output_segment_path}"
            raise RuntimeError(msg)
        size_bytes = output_segment_path.stat().st_size
        logger.info("Lucy: сегмент записан: %s (%s байт)", output_segment_path, size_bytes)
        if size_bytes < 512:
            logger.warning("Lucy: файл сегмента очень маленький — проверьте imageio/ffmpeg и кодек.")

    def _get_pipeline(self, model_id: str) -> Any:
        if self._pipeline is not None and getattr(self._pipeline, "model_id", None) == model_id:
            logger.info("pipeline: reuse cached LucyEditPipeline for %s", model_id)
            return self._pipeline

        logger.info("pipeline: loading weights for %s (first run / cold cache)...", model_id)
        use_cuda = self._config.device.startswith("cuda") and torch.cuda.is_available()
        torch_dtype = torch.bfloat16 if use_cuda else torch.float32
        local_files_only = os.environ.get("HF_LOCAL_FILES_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}
        logger.info("pipeline: local_files_only=%s", local_files_only)
        vae = AutoencoderKLWan.from_pretrained(
            model_id,
            subfolder="vae",
            torch_dtype=torch.float32,
            local_files_only=local_files_only,
        )
        pipeline = LucyEditPipeline.from_pretrained(
            model_id,
            vae=vae,
            torch_dtype=torch_dtype,
            local_files_only=local_files_only,
        )
        if use_cuda:
            pipeline.to(self._config.device)
        setattr(pipeline, "model_id", model_id)
        self._vae = vae
        self._pipeline = pipeline
        return pipeline

    def _extract_segment(
        self,
        source_path: Path,
        output_path: Path,
        start_second: float,
        end_second: float,
        video_cfg: MLConfig,
    ) -> None:
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
                f"scale={video_cfg.video_width}:{video_cfg.video_height},fps={video_cfg.video_fps}",
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
