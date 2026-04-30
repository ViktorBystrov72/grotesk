from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from grotesk.domain.processing.model import TimelineOperation
from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.video_pipeline import HuggingFaceVideoPipeline


def _cfg(tmp_path: Path) -> MLConfig:
    return MLConfig(
        media_storage_root=str(tmp_path),
        artifact_root=str(tmp_path),
        audio_model_id="a",
        speaker_model_id="s",
        audio_max_speakers=2,
        audio_dominant_speaker_ratio=0.7,
        audio_secondary_speaker_ratio=0.2,
        audio_short_turn_seconds=1.0,
        video_model_id="m",
        device="cpu",
        video_width=64,
        video_height=32,
        video_fps=8,
        video_max_frames=16,
        video_guidance_scale=3.0,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )


def test_build_effective_operations_and_prompt(tmp_path) -> None:
    p = HuggingFaceVideoPipeline(_cfg(tmp_path))
    ops = [TimelineOperation(start_second=0, end_second=1, prompt="x")]
    assert p._build_effective_operations(1.2, None, ops) == ops  # noqa: SLF001
    auto = p._build_effective_operations(1.2, " prompt ", [])  # noqa: SLF001
    assert auto[0].prompt == "prompt"
    with pytest.raises(ValueError):
        p._build_effective_operations(1.2, "", [])  # noqa: SLF001
    with pytest.raises(ValueError):
        p._build_effective_operations(2.0, None, [TimelineOperation(0, 3, "x")])  # noqa: SLF001
    with pytest.raises(ValueError):
        p._build_effective_operations(5.0, None, [TimelineOperation(1, 3, "x"), TimelineOperation(2, 4, "y")])  # noqa: SLF001
    assert p._compose_prompt("base", "edit") == "base. edit"  # noqa: SLF001
    assert p._compose_prompt(None, " edit ") == "edit"  # noqa: SLF001


def test_video_pipeline_commands_and_probe(tmp_path, monkeypatch) -> None:
    p = HuggingFaceVideoPipeline(_cfg(tmp_path))
    captured = {}
    monkeypatch.setattr(p, "_run_command", lambda command: captured.setdefault("commands", []).append(command))
    p._extract_segment(Path("s.mp4"), Path("o.mp4"), 0.0, 0.1)  # noqa: SLF001
    p._concatenate([Path("a.mp4"), Path("b.mp4")], tmp_path / "out.mp4")  # noqa: SLF001
    p._restore_audio(Path("s.mp4"), Path("v.mp4"), Path("f.mp4"))  # noqa: SLF001
    assert len(captured["commands"]) == 3

    monkeypatch.setattr(
        "grotesk.infrastructure.ml.video_pipeline.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="1.25"),
    )
    assert p._probe_duration(Path("x")) == 1.25  # noqa: SLF001


def test_video_pipeline_load_frames_and_run_command(tmp_path, monkeypatch) -> None:
    p = HuggingFaceVideoPipeline(_cfg(tmp_path))

    class _Cap:
        def __init__(self):
            self.calls = 0

        def isOpened(self):
            return True

        def read(self):
            self.calls += 1
            if self.calls > 2:
                return False, None
            return True, __import__("numpy").zeros((8, 8, 3), dtype="uint8")

        def release(self):
            return None

    monkeypatch.setattr("grotesk.infrastructure.ml.video_pipeline.cv2.VideoCapture", lambda _p: _Cap())
    frames = p._load_video_pil_frames(Path("a.mp4"), 4)  # noqa: SLF001
    assert isinstance(frames[0], Image.Image)

    class _BadCap(_Cap):
        def isOpened(self):
            return False

    monkeypatch.setattr("grotesk.infrastructure.ml.video_pipeline.cv2.VideoCapture", lambda _p: _BadCap())
    with pytest.raises(RuntimeError):
        p._load_video_pil_frames(Path("a.mp4"), 1)  # noqa: SLF001

    monkeypatch.setattr(
        "grotesk.infrastructure.ml.video_pipeline.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="boom"),
    )
    with pytest.raises(RuntimeError):
        HuggingFaceVideoPipeline._run_command(["ffmpeg"])  # noqa: SLF001


def test_video_pipeline_get_pipeline_and_edit_flow(tmp_path, monkeypatch) -> None:
    p = HuggingFaceVideoPipeline(_cfg(tmp_path))

    class _Pipe:
        def __call__(self, **kwargs):
            return SimpleNamespace(frames=[[b"x"]])

        def to(self, _d):
            return self

    monkeypatch.setattr(
        "grotesk.infrastructure.ml.video_pipeline.AutoencoderKLWan.from_pretrained", lambda *a, **k: object()
    )
    monkeypatch.setattr(
        "grotesk.infrastructure.ml.video_pipeline.LucyEditPipeline.from_pretrained", lambda *a, **k: _Pipe()
    )
    monkeypatch.setattr("grotesk.infrastructure.ml.video_pipeline.torch.cuda.is_available", lambda: False)
    first = p._get_pipeline("m")  # noqa: SLF001
    second = p._get_pipeline("m")  # noqa: SLF001
    assert first is second

    monkeypatch.setattr(p, "_probe_duration", lambda _path: 2.0)
    monkeypatch.setattr(p, "_extract_segment", lambda *a, **k: None)
    monkeypatch.setattr(p, "_run_model", lambda *a, **k: None)
    monkeypatch.setattr(p, "_concatenate", lambda *a, **k: None)
    monkeypatch.setattr(p, "_restore_audio", lambda s, c, o: Path(o).write_bytes(b"mp4"))
    out = p.edit(Path("source.mp4"), "m", "base", [TimelineOperation(0, 1, "edit")])
    assert out["operation_count"] == 1
