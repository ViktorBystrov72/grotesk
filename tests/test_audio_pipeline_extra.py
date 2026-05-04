from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from grotesk.infrastructure.ml.audio_pipeline import HuggingFaceAudioPipeline
from grotesk.infrastructure.ml.config import MLConfig


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
        video_model_id="v",
        device="cpu",
        video_width=64,
        video_height=64,
        video_fps=24,
        video_max_frames=8,
        video_guidance_scale=5.0,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )


def test_audio_pipeline_static_helpers(tmp_path) -> None:
    p = HuggingFaceAudioPipeline(_cfg(tmp_path))
    assert p._merge_speaker_segments([]) == []  # noqa: SLF001
    merged = p._merge_speaker_segments(  # noqa: SLF001
        [
            {"speaker": "s1", "start": 0.0, "end": 1.0, "text": "a"},
            {"speaker": "s1", "start": 1.0, "end": 2.0, "text": "b"},
        ]
    )
    assert merged[0]["end"] == 2.0
    assert p._reindex_labels([5, 5, 9]) == [0, 0, 1]  # noqa: SLF001
    assert p._compute_label_durations([1, 1, 2], [1.0, 2.0, 3.0])[1] == 3.0  # noqa: SLF001


def test_audio_pipeline_cluster_and_remap_helpers(tmp_path) -> None:
    p = HuggingFaceAudioPipeline(_cfg(tmp_path))
    labels = [0, 1, 2]
    embeddings = [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]]
    durations = [5.0, 1.0, 1.0]
    reduced = p._reduce_cluster_count(labels, embeddings, durations)  # noqa: SLF001
    assert len(reduced) == 3
    sparse = p._reduce_sparse_clusters([0, 1], [[1.0, 0.0], [0.0, 1.0]], [0.1, 0.1])  # noqa: SLF001
    assert len(set(sparse)) == 1
    remapped = p._remap_to_nearest_labels([2], [[0.0, 1.0]], [99])  # noqa: SLF001
    assert remapped == [2]


def test_audio_pipeline_assign_speaker_and_diarization_paths(tmp_path, monkeypatch) -> None:
    p = HuggingFaceAudioPipeline(_cfg(tmp_path))
    assert p._assign_speaker(0, 1, []) == "speaker_01"  # noqa: SLF001
    assert p._assign_speaker(0, 1, [{"speaker": "s", "start": 0.0, "end": 0.5}]) == "s"  # noqa: SLF001

    waveform = torch.zeros((1, 16000), dtype=torch.float32)
    monkeypatch.setattr(p, "_detect_speech_regions", lambda w, sr: [])
    assert p._build_diarization_segments(waveform, 16000) == []  # noqa: SLF001

    monkeypatch.setattr(p, "_detect_speech_regions", lambda w, sr: [(0, 100)])
    monkeypatch.setattr(
        p, "_get_speaker_classifier", lambda: SimpleNamespace(encode_batch=lambda x: torch.tensor([[0.1, 0.2]]))
    )
    single = p._build_diarization_segments(waveform, 16000)  # noqa: SLF001
    assert single[0]["speaker"] == "speaker_01"


def test_audio_pipeline_models_and_commands(tmp_path, monkeypatch) -> None:
    p = HuggingFaceAudioPipeline(_cfg(tmp_path))
    monkeypatch.setattr("grotesk.infrastructure.ml.audio_pipeline.torch.cuda.is_available", lambda: False)
    monkeypatch.setattr(
        "grotesk.infrastructure.ml.audio_pipeline.pipeline",
        lambda **kwargs: SimpleNamespace(model_id=kwargs["model"]),
    )
    first = p._get_asr_pipeline("a-model")  # noqa: SLF001
    second = p._get_asr_pipeline("a-model")  # noqa: SLF001
    assert first is second

    monkeypatch.setattr("grotesk.infrastructure.ml.audio_pipeline.load_silero_vad", lambda: "vad")
    assert p._get_vad_model() == "vad"  # noqa: SLF001
    assert p._get_vad_model() == "vad"  # noqa: SLF001

    monkeypatch.setattr(
        "grotesk.infrastructure.ml.audio_pipeline.EncoderClassifier.from_hparams",
        lambda **kwargs: "spk",
    )
    assert p._get_speaker_classifier() == "spk"  # noqa: SLF001
    assert p._get_speaker_classifier() == "spk"  # noqa: SLF001

    monkeypatch.setattr(
        "grotesk.infrastructure.ml.audio_pipeline.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="boom"),
    )
    with pytest.raises(RuntimeError):
        p._run_command(["ffmpeg"])  # noqa: SLF001
