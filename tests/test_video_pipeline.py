from pathlib import Path

from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.video_pipeline import HuggingFaceVideoPipeline


def build_config() -> MLConfig:
    return MLConfig(
        media_storage_root="/tmp/grotesk-media",
        artifact_root="/tmp/grotesk-media/results",
        audio_model_id="openai/whisper-large-v3-turbo",
        speaker_model_id="speechbrain/spkrec-ecapa-voxceleb",
        audio_max_speakers=3,
        audio_dominant_speaker_ratio=0.72,
        audio_secondary_speaker_ratio=0.18,
        audio_short_turn_seconds=1.8,
        video_model_id="decart-ai/Lucy-Edit-Dev",
        device="cpu",
        video_width=576,
        video_height=320,
        video_fps=24,
        video_max_frames=33,
        video_guidance_scale=5.0,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )


class DummyPipe:
    def __init__(self) -> None:
        self.scheduler = type("Scheduler", (), {"config": {"name": "dummy"}})()

    def __call__(self, **kwargs):
        self.last_kwargs = kwargs
        return type("Result", (), {"frames": [[b"frame"]]})()


def test_get_pipeline_loads_lucy(monkeypatch) -> None:
    config = build_config()
    pipeline = HuggingFaceVideoPipeline(config)
    vae = object()
    lucy_pipe = DummyPipe()

    monkeypatch.setattr(
        "grotesk.infrastructure.ml.video_pipeline.AutoencoderKLWan.from_pretrained",
        lambda *args, **kwargs: vae,
    )
    monkeypatch.setattr(
        "grotesk.infrastructure.ml.video_pipeline.LucyEditPipeline.from_pretrained",
        lambda *args, **kwargs: lucy_pipe,
    )

    result = pipeline._get_pipeline(config.video_model_id)

    assert result is lucy_pipe
    assert getattr(result, "model_id") == config.video_model_id


def test_run_model_uses_expected_num_frames(monkeypatch) -> None:
    config = build_config()
    pipeline = HuggingFaceVideoPipeline(config)
    lucy_pipe = DummyPipe()

    monkeypatch.setattr(pipeline, "_get_pipeline", lambda _model_id: lucy_pipe)
    monkeypatch.setattr(pipeline, "_probe_duration", lambda _path: 1.0)
    monkeypatch.setattr(pipeline, "_load_video_pil_frames", lambda _path, num_frames: ["frame"] * num_frames)
    monkeypatch.setattr("grotesk.infrastructure.ml.video_pipeline.export_to_video", lambda *args, **kwargs: None)

    pipeline._run_model(
        Path("/tmp/input.mp4"),
        Path("/tmp/output.mp4"),
        model_id=config.video_model_id,
        prompt="make it brighter",
    )

    assert lucy_pipe.last_kwargs["num_frames"] == 24
