from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from grotesk.domain.catalog.model import Capability, ModelId, ModelProfile
from grotesk.domain.common.primitives import FileLocation, Money
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.media_ingestion.model import MediaAsset, MediaAssetId, MediaType
from grotesk.domain.processing.model import JobId, JobType, ProcessingJob, TimelineOperation
from grotesk.infrastructure.ml.artifacts import ResultArtifactStore
from grotesk.infrastructure.ml.config import MLConfig
from grotesk.infrastructure.ml.processor import HuggingFaceJobProcessor
from grotesk.infrastructure.ml.transcription_formatting import (
    build_book_transcript,
    build_transcript_turns,
    dump_json_pretty,
    format_speaker_name,
    prepare_transcription_artifact,
)
from grotesk.infrastructure.ml.types import JobExecutionResult
from grotesk.presentation.web.routes import (
    filter_models_by_capability,
    format_duration_seconds,
    normalize_cabinet_job_limit,
    normalize_cabinet_job_page,
    parse_operations_text,
    resolve_job_duration_label,
)


def _cfg(tmp_path: Path) -> MLConfig:
    return MLConfig(
        media_storage_root=str(tmp_path),
        artifact_root=str(tmp_path / "results"),
        audio_model_id="audio-model",
        speaker_model_id="speaker-model",
        audio_max_speakers=2,
        audio_dominant_speaker_ratio=0.7,
        audio_secondary_speaker_ratio=0.2,
        audio_short_turn_seconds=1.0,
        video_model_id="video-model",
        device="cpu",
        video_width=320,
        video_height=240,
        video_fps=24,
        video_max_frames=25,
        video_guidance_scale=5.0,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )


def _job(job_type: JobType) -> ProcessingJob:
    return ProcessingJob(
        id=JobId(UUID("00000000-0000-0000-0000-000000000001")),
        user_id=UserId(UUID("00000000-0000-0000-0000-000000000002")),
        media_asset_id=MediaAssetId(UUID("00000000-0000-0000-0000-000000000003")),
        model_id=ModelId(UUID("00000000-0000-0000-0000-000000000004")),
        job_type=job_type,
        estimated_cost=Money(Decimal("1.0")),
        prompt_text="prompt",
        operations=[TimelineOperation(start_second=0, end_second=1, prompt="edit")],
    )


def _media(path: Path) -> MediaAsset:
    return MediaAsset(
        id=MediaAssetId(UUID("00000000-0000-0000-0000-000000000003")),
        owner_id=UserId(UUID("00000000-0000-0000-0000-000000000002")),
        media_type=MediaType.AUDIO,
        location=FileLocation(str(path)),
    )


@pytest.mark.asyncio
async def test_hf_job_processor_paths(tmp_path, monkeypatch) -> None:
    source_path = tmp_path / "a.wav"
    source_path.write_bytes(b"data")
    processor = HuggingFaceJobProcessor(_cfg(tmp_path))

    monkeypatch.setattr(
        processor._audio_pipeline,
        "transcribe",
        lambda path, model_id: {"text": "hello", "speaker_count": 2, "turns": [], "model_name": model_id},
    )
    monkeypatch.setattr(
        processor._video_pipeline,
        "edit",
        lambda path, model_id, prompt_text, operations: {
            "output_path": tmp_path / "out.mp4",
            "model_name": model_id,
            "operation_count": len(operations),
            "width": 320,
            "height": 240,
            "fps": 24,
        },
    )

    model = ModelProfile(
        id=ModelId(UUID("00000000-0000-0000-0000-000000000004")),
        name="custom-model",
        capabilities=[Capability.TRANSCRIPTION],
        pricing_rules=[],
    )
    transcription = await processor.process(_job(JobType.TRANSCRIPTION), _media(source_path), model)
    assert transcription.result_type == "transcription"
    assert transcription.history_payload["model_name"] == "custom-model"

    video_model = ModelProfile(
        id=model.id,
        name="video-custom",
        capabilities=[Capability.VIDEO_EDITING],
        pricing_rules=[],
    )
    video = await processor.process(_job(JobType.VIDEO_EDITING), _media(source_path), video_model)
    assert video.result_type == "video_editing"
    assert video.artifact_source == tmp_path / "out.mp4"

    missing = _media(tmp_path / "missing.wav")
    with pytest.raises(FileNotFoundError):
        await processor.process(_job(JobType.TRANSCRIPTION), missing, model)


@pytest.mark.asyncio
async def test_hf_job_processor_unsupported_job_type(tmp_path) -> None:
    processor = HuggingFaceJobProcessor(_cfg(tmp_path))

    class _Unknown:
        value = "unknown"

    unknown_job = _job(JobType.TRANSCRIPTION)
    unknown_job.job_type = _Unknown()  # type: ignore[assignment]
    path = tmp_path / "a.wav"
    path.write_bytes(b"data")
    with pytest.raises(ValueError, match="Unsupported job type"):
        await processor.process(
            unknown_job,  # type: ignore[arg-type]
            _media(path),
            ModelProfile(id=unknown_job.model_id, name="", capabilities=[], pricing_rules=[]),
        )


def test_artifact_store_save_json_and_binary(tmp_path) -> None:
    store = ResultArtifactStore(tmp_path)
    rid = UUID("00000000-0000-0000-0000-000000000010")
    json_path = store.save(
        rid,
        JobExecutionResult(
            result_type="transcription",
            artifact_extension=".json",
            artifact_payload={"text": "ok"},
            history_payload={},
        ),
    )
    assert json_path.exists()

    source = tmp_path / "src.bin"
    source.write_bytes(b"x")
    bin_path = store.save(
        UUID("00000000-0000-0000-0000-000000000011"),
        JobExecutionResult(
            result_type="video_editing",
            artifact_extension=".mp4",
            artifact_source=source,
            history_payload={},
        ),
    )
    assert bin_path.exists()
    with pytest.raises(ValueError):
        store.save(
            UUID("00000000-0000-0000-0000-000000000012"),
            JobExecutionResult(
                result_type="video_editing",
                artifact_extension=".mp4",
                history_payload={},
            ),
        )


def test_transcription_formatting_helpers() -> None:
    assert format_speaker_name(None) == "Спикер"
    assert format_speaker_name("speaker_02") == "Спикер 2"
    assert format_speaker_name("john_doe") == "John Doe"

    turns = build_transcript_turns(
        {
            "turns": [{"speaker": "speaker_01", "text": " hi "}, {"speaker": "speaker_02", "text": ""}, "bad"],
            "segments": [],
        }
    )
    assert turns == [{"speaker": "Спикер 1", "text": "hi"}]

    merged = build_transcript_turns(
        {
            "segments": [
                {"speaker": "speaker_01", "text": "a"},
                {"speaker": "speaker_01", "text": "b"},
                {"speaker": "speaker_02", "text": "c"},
            ]
        }
    )
    assert merged[0]["text"] == "a b"
    assert build_book_transcript({"text": "  plain  "}) == "plain"
    assert build_book_transcript(None) is None
    prepared = prepare_transcription_artifact({"text": "x", "turns": [], "duration_seconds": 1.2, "model_name": "m"})
    assert prepared["text"] == "x"
    assert dump_json_pretty({"a": 1}) is not None
    assert dump_json_pretty(None) is None


def test_routes_helper_functions(monkeypatch) -> None:
    assert normalize_cabinet_job_limit(5) == 5
    assert normalize_cabinet_job_limit(13) == 10
    assert normalize_cabinet_job_page(0, total_jobs=100, job_limit=10) == 1
    assert normalize_cabinet_job_page(99, total_jobs=10, job_limit=10) == 1
    assert format_duration_seconds(None) == "—"
    assert format_duration_seconds(5) == "5 сек"
    assert format_duration_seconds(125) == "2 мин 5 сек"
    assert format_duration_seconds(3723) == "1 ч 2 мин 3 сек"

    monkeypatch.setattr("grotesk.presentation.web.routes.probe_media_duration_seconds", lambda _key: 9.2)
    assert resolve_job_duration_label("x", {"duration_seconds": 3}) == "9 сек"
    monkeypatch.setattr("grotesk.presentation.web.routes.probe_media_duration_seconds", lambda _key: None)
    assert resolve_job_duration_label("x", {"duration_seconds": 3}) == "3 сек"
    assert resolve_job_duration_label("x", {"duration_seconds": "bad"}) == "—"

    models = [
        SimpleNamespace(capabilities=[Capability.TRANSCRIPTION]),
        SimpleNamespace(capabilities=[Capability.VIDEO_EDITING]),
    ]
    filtered = filter_models_by_capability(models, Capability.VIDEO_EDITING)
    assert len(filtered) == 1

    ok_ops, err = parse_operations_text("00:01|00:03|hello")
    assert err is None
    assert len(ok_ops) == 1
    bad_ops, err = parse_operations_text("broken")
    assert bad_ops == []
    assert err is not None
