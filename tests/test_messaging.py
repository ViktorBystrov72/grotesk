import os
import tempfile
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from grotesk.domain.catalog.model import Capability, ModelId, ModelProfile, PricingRule
from grotesk.domain.common.primitives import FileLocation, Money
from grotesk.domain.identity_access.model import Credential, Email, PasswordHash, User, UserId, UserRole
from grotesk.domain.media_ingestion.model import MediaAsset, MediaAssetId, MediaType
from grotesk.domain.processing.events import TranscriptionJobSubmitted
from grotesk.domain.processing.model import JobId, JobType, ProcessingJob
from grotesk.infrastructure.db.config import DBConfig
from grotesk.infrastructure.db.init_data import create_schema
from grotesk.infrastructure.db.repositories.catalog import ModelCatalogRepositoryImpl
from grotesk.infrastructure.db.repositories.media import MediaAssetRepositoryImpl
from grotesk.infrastructure.db.repositories.processing import ProcessingJobRepositoryImpl
from grotesk.infrastructure.db.repositories.user import UserRepositoryImpl
from grotesk.infrastructure.db.session import build_engine, build_session_factory
from grotesk.infrastructure.messaging.config import MessagingConfig
from grotesk.infrastructure.messaging.messages import JobSubmittedMessage
from grotesk.infrastructure.messaging.worker import ProcessingWorker


@pytest_asyncio.fixture
async def db_context() -> dict[str, object]:
    db_file = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    db_file.close()
    db_path = Path(db_file.name)
    engine = build_engine(
        DBConfig(
            driver="sqlite+aiosqlite",
            host="",
            port=0,
            database=db_file.name,
            user="",
            password="",
            echo=False,
        ),
    )
    session_factory = build_session_factory(engine)
    await create_schema(engine)

    try:
        yield {
            "engine": engine,
            "session_factory": session_factory,
        }
    finally:
        await engine.dispose()
        os.unlink(db_path)


def test_job_submitted_message_roundtrip() -> None:
    event = TranscriptionJobSubmitted(job_id=JobId(UUID("00000000-0000-0000-0000-000000000123")))

    payload = JobSubmittedMessage.from_event(event)

    assert payload is not None
    restored_payload = JobSubmittedMessage.from_body(payload.to_body())
    assert restored_payload == payload
    assert restored_payload.job_type == "transcription"


@pytest.mark.asyncio
async def test_worker_processes_job_and_saves_result(db_context: dict[str, object]) -> None:
    session_factory = db_context["session_factory"]
    user_id = UserId(uuid4())
    media_asset_id = MediaAssetId(uuid4())
    model_id = ModelId(uuid4())
    job_id = JobId(uuid4())

    async with session_factory() as session:
        user_repository = UserRepositoryImpl(session)
        media_repository = MediaAssetRepositoryImpl(session)
        model_repository = ModelCatalogRepositoryImpl(session)
        processing_repository = ProcessingJobRepositoryImpl(session)

        await user_repository.add(
            User(
                id=user_id,
                credential=Credential(
                    email=Email("worker-test@grotesk.local"),
                    password_hash=PasswordHash("hash"),
                ),
                role=UserRole.CUSTOMER,
            ),
        )
        await media_repository.add(
            MediaAsset(
                id=media_asset_id,
                owner_id=user_id,
                media_type=MediaType.AUDIO,
                location=FileLocation("/tmp/audio.wav"),
            ),
        )
        await model_repository.save(
            ModelProfile(
                id=model_id,
                name="worker-model",
                capabilities=[Capability.TRANSCRIPTION],
                pricing_rules=[PricingRule(Capability.TRANSCRIPTION, Money(Decimal("1")))],
            ),
        )

        job = ProcessingJob(
            id=job_id,
            user_id=user_id,
            media_asset_id=media_asset_id,
            model_id=model_id,
            job_type=JobType.TRANSCRIPTION,
            estimated_cost=Money(Decimal("10")),
        )
        job.queue()
        await processing_repository.add(job)
        await session.commit()

    worker = ProcessingWorker(
        session_factory,
        MessagingConfig(
            backend="rabbitmq",
            amqp_url="amqp://guest:guest@localhost:5672/",
            queue_name="ml_tasks",
            prefetch_count=1,
            durable_queue=True,
            worker_id="test-worker",
            processing_delay_seconds=0,
        ),
    )
    payload = JobSubmittedMessage(
        event_name="TranscriptionJobSubmitted",
        job_id=job_id.value,
        job_type="transcription",
        submitted_at="2026-01-01T12:00:00+00:00",
    )

    await worker.process_message(payload)

    async with session_factory() as session:
        processing_repository = ProcessingJobRepositoryImpl(session)
        saved_job = await processing_repository.get_by_id(job_id)

        assert saved_job is not None
        assert saved_job.status.value == "completed"
        assert saved_job.result_ref is not None
        assert "test-worker" in saved_job.history[-1].message
        assert "Mock transcription completed successfully." in saved_job.history[-1].message
