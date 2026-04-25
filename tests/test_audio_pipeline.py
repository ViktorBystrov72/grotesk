from pathlib import Path

import pytest
import torch

from grotesk.infrastructure.ml.audio_pipeline import HuggingFaceAudioPipeline
from grotesk.infrastructure.ml.config import MLConfig


def test_audio_pipeline_transcribe_uses_raw_waveform(monkeypatch, tmp_path) -> None:
    config = MLConfig(
        media_storage_root=str(tmp_path),
        artifact_root=str(tmp_path),
        audio_model_id="audio-model",
        speaker_model_id="speaker-model",
        audio_max_speakers=3,
        audio_dominant_speaker_ratio=0.72,
        audio_secondary_speaker_ratio=0.18,
        audio_short_turn_seconds=1.8,
        video_model_id="video-model",
        device="cpu",
        video_width=832,
        video_height=480,
        video_fps=24,
        video_max_frames=81,
        video_guidance_scale=5.0,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )
    pipeline = HuggingFaceAudioPipeline(config)
    normalized_path = tmp_path / "normalized.wav"
    normalized_path.write_bytes(b"wav")
    captured: dict[str, object] = {}

    def fake_normalize(source_path: Path) -> Path:
        assert source_path.name == "sample.ogg"
        return normalized_path

    def fake_load_waveform(path: Path) -> tuple[torch.Tensor, int]:
        assert path == normalized_path
        return torch.tensor([[0.1, -0.2, 0.3]], dtype=torch.float32), 16000

    def fake_asr_pipeline(inputs, **kwargs):
        captured["inputs"] = inputs
        captured["kwargs"] = kwargs
        return {"text": "test", "language": "ru", "chunks": []}

    monkeypatch.setattr(pipeline, "_normalize_audio", fake_normalize)
    monkeypatch.setattr(pipeline, "_load_waveform", fake_load_waveform)
    monkeypatch.setattr(pipeline, "_get_asr_pipeline", lambda model_id: fake_asr_pipeline)

    result = pipeline.transcribe(tmp_path / "sample.ogg", "model-id")

    assert result["text"] == "test"
    assert result["language"] == "russian"
    inputs = captured["inputs"]
    assert isinstance(inputs, dict)
    assert inputs["sampling_rate"] == 16000
    assert inputs["raw"].tolist() == pytest.approx([0.1, -0.2, 0.3])
    assert captured["kwargs"] == {
        "return_timestamps": True,
        "generate_kwargs": {"task": "transcribe", "language": "russian"},
    }


def test_audio_pipeline_assigns_speakers_from_diarization_segments(tmp_path, monkeypatch) -> None:
    config = MLConfig(
        media_storage_root=str(tmp_path),
        artifact_root=str(tmp_path),
        audio_model_id="audio-model",
        speaker_model_id="speechbrain/spkrec-ecapa-voxceleb",
        audio_max_speakers=3,
        audio_dominant_speaker_ratio=0.72,
        audio_secondary_speaker_ratio=0.18,
        audio_short_turn_seconds=1.8,
        video_model_id="video-model",
        device="cpu",
        video_width=832,
        video_height=480,
        video_fps=24,
        video_max_frames=81,
        video_guidance_scale=5.0,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )
    pipeline = HuggingFaceAudioPipeline(config)
    monkeypatch.setattr(
        pipeline,
        "_load_waveform",
        lambda _path: (torch.zeros((1, 16000 * 20), dtype=torch.float32), 16000),
    )
    monkeypatch.setattr(
        pipeline,
        "_build_diarization_segments",
        lambda _waveform, _sample_rate: [
            {"speaker": "speaker_02", "start": 0.0, "end": 2.0},
            {"speaker": "speaker_01", "start": 2.0, "end": 20.0},
        ],
    )

    segments = pipeline._build_segments(
        tmp_path / "sample.wav",
        [
            {"timestamp": (0.0, 1.5), "text": "Короткая первая реплика"},
            {"timestamp": (3.0, 8.0), "text": "Длинная основная реплика"},
        ],
    )

    assert segments[0]["speaker"] == "speaker_02"
    assert segments[1]["speaker"] == "speaker_01"


def test_audio_pipeline_limits_cluster_count_and_collapses_minor_speakers(tmp_path) -> None:
    config = MLConfig(
        media_storage_root=str(tmp_path),
        artifact_root=str(tmp_path),
        audio_model_id="audio-model",
        speaker_model_id="speechbrain/spkrec-ecapa-voxceleb",
        audio_max_speakers=2,
        audio_dominant_speaker_ratio=0.72,
        audio_secondary_speaker_ratio=0.18,
        audio_short_turn_seconds=1.8,
        video_model_id="video-model",
        device="cpu",
        video_width=832,
        video_height=480,
        video_fps=24,
        video_max_frames=81,
        video_guidance_scale=5.0,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )
    pipeline = HuggingFaceAudioPipeline(config)

    labels = pipeline._collapse_to_dominant_speakers(
        labels=[0, 0, 0, 1, 2],
        embeddings=[
            [1.0, 0.0],
            [0.98, 0.02],
            [0.99, 0.01],
            [0.1, 0.9],
            [0.2, 0.8],
        ],
        durations=[10.0, 8.0, 7.0, 1.0, 0.8],
    )

    assert len(set(labels)) == 1


def test_audio_pipeline_merges_short_intrusive_turns(tmp_path) -> None:
    config = MLConfig(
        media_storage_root=str(tmp_path),
        artifact_root=str(tmp_path),
        audio_model_id="audio-model",
        speaker_model_id="speechbrain/spkrec-ecapa-voxceleb",
        audio_max_speakers=3,
        audio_dominant_speaker_ratio=0.72,
        audio_secondary_speaker_ratio=0.18,
        audio_short_turn_seconds=1.8,
        video_model_id="video-model",
        device="cpu",
        video_width=832,
        video_height=480,
        video_fps=24,
        video_max_frames=81,
        video_guidance_scale=5.0,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )
    pipeline = HuggingFaceAudioPipeline(config)

    merged = pipeline._merge_short_turns(
        [
            {"speaker": "speaker_01", "start": 0.0, "end": 6.0},
            {"speaker": "speaker_02", "start": 6.0, "end": 6.5},
            {"speaker": "speaker_01", "start": 6.5, "end": 15.0},
        ]
    )

    assert merged == [{"speaker": "speaker_01", "start": 0.0, "end": 15.0}]
