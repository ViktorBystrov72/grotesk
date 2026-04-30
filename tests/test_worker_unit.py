from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import UUID

import pytest

from grotesk.domain.processing.model import JobId
from grotesk.infrastructure.messaging.config import MessagingConfig
from grotesk.infrastructure.messaging.messages import JobSubmittedMessage
from grotesk.infrastructure.messaging.worker import JobNotReadyError, ProcessingWorker


def _cfg() -> MessagingConfig:
    return MessagingConfig(
        backend="rabbitmq",
        amqp_url="amqp://guest:guest@localhost:5672/",
        queue_name="ml_tasks",
        prefetch_count=1,
        durable_queue=True,
        worker_id="worker-test",
        processing_delay_seconds=0.0,
    )


def _payload() -> JobSubmittedMessage:
    return JobSubmittedMessage(
        event_name="TranscriptionJobSubmitted",
        job_id=UUID("00000000-0000-0000-0000-000000000111"),
        job_type="transcription",
        submitted_at="2024-01-01T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_consume_message_ack_and_nack_paths(monkeypatch) -> None:
    worker = ProcessingWorker(session_factory=SimpleNamespace(), messaging_config=_cfg(), processor=SimpleNamespace())  # type: ignore[arg-type]

    class _Msg:
        def __init__(self):
            self.body = _payload().to_body()
            self.acked = False
            self.nacked = False
            self.requeue = None

        async def ack(self):
            self.acked = True

        async def nack(self, requeue: bool):
            self.nacked = True
            self.requeue = requeue

    msg = _Msg()
    monkeypatch.setattr(worker, "process_message", lambda _p: asyncio.sleep(0))
    await worker._consume_message(msg)  # noqa: SLF001
    assert msg.acked is True

    msg_not_ready = _Msg()

    async def _raise_not_ready(_p):
        raise JobNotReadyError("not ready")

    monkeypatch.setattr(worker, "process_message", _raise_not_ready)
    await worker._consume_message(msg_not_ready)  # noqa: SLF001
    assert msg_not_ready.nacked is True
    assert msg_not_ready.requeue is True

    msg_bad = _Msg()
    msg_bad.body = b"{bad json"
    await worker._consume_message(msg_bad)  # noqa: SLF001
    assert msg_bad.acked is True


@pytest.mark.asyncio
async def test_wait_for_processing_slot_and_build_message(monkeypatch, tmp_path) -> None:
    worker = ProcessingWorker(session_factory=SimpleNamespace(), messaging_config=_cfg(), processor=SimpleNamespace())  # type: ignore[arg-type]
    job_id = JobId(UUID("00000000-0000-0000-0000-000000000111"))

    monkeypatch.setattr(worker, "_is_job_canceled", lambda _job_id: asyncio.sleep(0, result=False))
    await worker._wait_for_processing_slot(job_id)  # noqa: SLF001

    completion = worker._build_completion_message(  # noqa: SLF001
        payload=_payload(),
        job_type="transcription",
        artifact_path=tmp_path / "a.json",
        payload_data={"status": "done"},
    )
    parsed = json.loads(completion)
    assert parsed["job_id"] == "00000000-0000-0000-0000-000000000111"
    assert parsed["worker_id"] == "worker-test"
    assert parsed["result"] == {"status": "done"}


def test_read_execution_result_parses_payload(tmp_path) -> None:
    result_path = tmp_path / "execution.json"
    result_path.write_text(
        json.dumps(
            {
                "result_type": "transcription",
                "artifact_extension": "json",
                "history_payload": {"x": 1},
                "artifact_payload": {"text": "ok"},
                "artifact_source": str(tmp_path / "artifact.json"),
            }
        ),
        encoding="utf-8",
    )
    result = ProcessingWorker._read_execution_result(result_path)  # noqa: SLF001
    assert result.result_type == "transcription"
    assert result.artifact_source == tmp_path / "artifact.json"


@pytest.mark.asyncio
async def test_terminate_process_paths(monkeypatch) -> None:
    class _Process:
        def __init__(self):
            self.returncode = None
            self.terminated = False
            self.killed = False
            self.wait_calls = 0

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        async def wait(self):
            self.wait_calls += 1
            return 0

        async def communicate(self):
            return (b"", b"")

    process = _Process()
    await ProcessingWorker._terminate_process(process)  # noqa: SLF001
    assert process.terminated is True

    process_timeout = _Process()

    async def _timeout(_awaitable, timeout):
        _awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr("grotesk.infrastructure.messaging.worker.asyncio.wait_for", _timeout)
    await ProcessingWorker._terminate_process(process_timeout)  # noqa: SLF001
    assert process_timeout.killed is True
