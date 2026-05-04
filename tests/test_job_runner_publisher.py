from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from grotesk.domain.common.event import Event
from grotesk.domain.processing.events import TranscriptionJobSubmitted, VideoEditingJobSubmitted
from grotesk.domain.processing.model import JobId
from grotesk.infrastructure.messaging.config import MessagingConfig
from grotesk.infrastructure.messaging.job_runner import main, run_job, serialize_execution_result
from grotesk.infrastructure.messaging.messages import JobSubmittedMessage
from grotesk.infrastructure.messaging.publisher import RabbitMQEventPublisher
from grotesk.infrastructure.ml.types import JobExecutionResult


def _uuid(value: str) -> UUID:
    return UUID(value)


def test_job_submitted_message_roundtrip_and_unknown_event() -> None:
    job_id = JobId(_uuid("00000000-0000-0000-0000-000000000111"))
    event = TranscriptionJobSubmitted(job_id=job_id, occurred_at=datetime(2024, 1, 1, tzinfo=UTC))
    message = JobSubmittedMessage.from_event(event)
    assert message is not None
    assert message.job_identifier == job_id
    body = message.to_body()
    decoded = JobSubmittedMessage.from_body(body)
    assert decoded == message

    video_event = VideoEditingJobSubmitted(job_id=job_id, occurred_at=datetime(2024, 1, 2, tzinfo=UTC))
    assert JobSubmittedMessage.from_event(video_event) is not None

    assert JobSubmittedMessage.from_event(Event()) is None


def test_serialize_execution_result_works_with_and_without_source() -> None:
    with_source = JobExecutionResult(
        result_type="transcription",
        artifact_extension="json",
        history_payload={"a": 1},
        artifact_payload={"text": "ok"},
        artifact_source=Path("/tmp/file.json"),
    )
    without_source = JobExecutionResult(
        result_type="transcription",
        artifact_extension="json",
        history_payload={},
        artifact_payload={},
        artifact_source=None,
    )

    serialized_with_source = serialize_execution_result(with_source)
    serialized_without_source = serialize_execution_result(without_source)
    assert serialized_with_source["artifact_source"] == "/tmp/file.json"
    assert serialized_without_source["artifact_source"] is None


@pytest.mark.asyncio
async def test_run_job_success_and_not_found_cases(tmp_path, monkeypatch) -> None:
    disposed = {"value": False}

    class _Engine:
        async def dispose(self):
            disposed["value"] = True

    class _SessionScope:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class _ProcessingRepo:
        def __init__(self, _session):
            pass

        async def get_by_id(self, _job_id):
            return SimpleNamespace(
                media_asset_id=SimpleNamespace(value=_uuid("00000000-0000-0000-0000-000000000211")),
                model_id=SimpleNamespace(value=_uuid("00000000-0000-0000-0000-000000000311")),
            )

    class _MediaRepo:
        def __init__(self, _session):
            pass

        async def get_by_id(self, _media_asset_id):
            return SimpleNamespace()

    class _ModelRepo:
        def __init__(self, _session):
            pass

        async def get_by_id(self, _model_id):
            return SimpleNamespace()

    class _Processor:
        def __init__(self, _config):
            pass

        async def process(self, _job, _media, _model):
            return JobExecutionResult(
                result_type="transcription",
                artifact_extension="json",
                history_payload={"status": "ok"},
                artifact_payload={"text": "done"},
                artifact_source=None,
            )

    monkeypatch.setattr("grotesk.infrastructure.messaging.job_runner.build_engine", lambda _cfg: _Engine())
    monkeypatch.setattr("grotesk.infrastructure.messaging.job_runner.build_session_factory", lambda _e: object())
    monkeypatch.setattr("grotesk.infrastructure.messaging.job_runner.session_scope", lambda _sf: _SessionScope())
    monkeypatch.setattr("grotesk.infrastructure.messaging.job_runner.HuggingFaceJobProcessor", _Processor)
    monkeypatch.setattr("grotesk.infrastructure.messaging.job_runner.ProcessingJobRepositoryImpl", _ProcessingRepo)
    monkeypatch.setattr("grotesk.infrastructure.messaging.job_runner.MediaAssetRepositoryImpl", _MediaRepo)
    monkeypatch.setattr("grotesk.infrastructure.messaging.job_runner.ModelCatalogRepositoryImpl", _ModelRepo)
    monkeypatch.setattr(
        "grotesk.infrastructure.messaging.job_runner.DBConfig.from_env",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "grotesk.infrastructure.messaging.job_runner.MLConfig.from_env",
        lambda: SimpleNamespace(),
    )

    out = tmp_path / "result.json"
    await run_job(JobId(_uuid("00000000-0000-0000-0000-000000000999")), out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["result_type"] == "transcription"
    assert disposed["value"] is True

    class _MissingProcessingRepo(_ProcessingRepo):
        async def get_by_id(self, _job_id):
            return None

    monkeypatch.setattr(
        "grotesk.infrastructure.messaging.job_runner.ProcessingJobRepositoryImpl", _MissingProcessingRepo
    )
    with pytest.raises(ValueError, match="does not exist"):
        await run_job(JobId(_uuid("00000000-0000-0000-0000-000000000999")), tmp_path / "x.json")


def test_main_usage_and_success(monkeypatch, tmp_path) -> None:
    called = {}

    async def _fake_run_job(job_id, result_path):
        called["job_id"] = job_id
        called["result_path"] = result_path

    monkeypatch.setattr("grotesk.infrastructure.messaging.job_runner.run_job", _fake_run_job)
    monkeypatch.setattr("grotesk.infrastructure.messaging.job_runner.sys.argv", ["prog"])
    with pytest.raises(SystemExit, match="Usage:"):
        main()

    monkeypatch.setattr(
        "grotesk.infrastructure.messaging.job_runner.sys.argv",
        ["prog", "00000000-0000-0000-0000-000000000111", str(tmp_path / "r.json")],
    )
    main()
    assert str(called["job_id"].value) == "00000000-0000-0000-0000-000000000111"


@pytest.mark.asyncio
async def test_rabbitmq_publisher_publishes_and_skips(monkeypatch) -> None:
    published = []

    class _Exchange:
        async def publish(self, message, routing_key):
            published.append((message, routing_key))

    class _Channel:
        def __init__(self):
            self.default_exchange = _Exchange()

        async def declare_queue(self, name, durable):
            return SimpleNamespace(name=name, durable=durable)

    class _Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def channel(self):
            return _Channel()

    async def _connect(_url):
        return _Connection()

    monkeypatch.setattr("grotesk.infrastructure.messaging.publisher.connect_robust", _connect)

    cfg = MessagingConfig(
        backend="rabbitmq",
        amqp_url="amqp://guest:guest@localhost:5672/",
        queue_name="ml_tasks",
        prefetch_count=1,
        durable_queue=True,
        worker_id="w1",
        processing_delay_seconds=0.5,
    )
    publisher = RabbitMQEventPublisher(cfg)
    job_id = JobId(_uuid("00000000-0000-0000-0000-000000000111"))
    event = TranscriptionJobSubmitted(job_id=job_id, occurred_at=datetime(2024, 1, 1, tzinfo=UTC))
    await publisher.publish([event, Event()])
    assert len(published) == 1
    assert published[0][1] == "ml_tasks"

    published.clear()
    await publisher.publish([Event()])
    assert published == []
