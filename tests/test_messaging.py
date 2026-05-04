from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from grotesk.application.processing.commands import CancelProcessingJob
from grotesk.domain.billing.model import (
    AccountBalance,
    BillingTransaction,
    CreditReservation,
    TransactionId,
    TransactionType,
)
from grotesk.domain.catalog.model import Capability, ModelId, ModelProfile, PricingRule
from grotesk.domain.common.primitives import FileLocation, Money
from grotesk.domain.identity_access.model import Credential, Email, PasswordHash, User, UserId, UserRole
from grotesk.domain.media_ingestion.model import MediaAsset, MediaAssetId, MediaType
from grotesk.domain.processing.events import TranscriptionJobSubmitted
from grotesk.domain.processing.model import JobId, JobType, ProcessingJob, ProcessingStatus, TimelineOperation
from grotesk.infrastructure.messaging.messages import JobSubmittedMessage
from grotesk.infrastructure.messaging.worker import ProcessingWorker
from grotesk.infrastructure.ml.artifacts import ResultArtifactStore
from grotesk.infrastructure.ml.types import JobExecutionResult
from grotesk.main.bootstrap import build_application
from tests.support import (
    DBContext,
    build_messaging_assertion_repositories,
    build_messaging_seed_repositories,
    build_test_messaging_config,
)


class FakeProcessor:
    def __init__(self, result: JobExecutionResult | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def process(
        self,
        job: ProcessingJob,
        media_asset: MediaAsset,
        model_profile: ModelProfile,
    ) -> JobExecutionResult:
        if self._error is not None:
            raise self._error
        if self._result is None:
            raise AssertionError("Fake processor result must be configured.")
        return self._result


@dataclass(frozen=True)
class TranscriptionJobSetup:
    user_id: UserId
    media_asset_id: MediaAssetId
    model_id: ModelId
    job_id: JobId


@dataclass(frozen=True)
class MessagingAssertionState:
    job: ProcessingJob | None
    balance: AccountBalance | None
    transactions: list[BillingTransaction]


async def seed_transcription_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_email: str,
    model_name: str,
    reserved_balance: Decimal = Decimal("90"),
    reservation_amount: Decimal = Decimal("10"),
) -> TranscriptionJobSetup:
    setup = TranscriptionJobSetup(
        user_id=UserId(uuid4()),
        media_asset_id=MediaAssetId(uuid4()),
        model_id=ModelId(uuid4()),
        job_id=JobId(uuid4()),
    )

    async with session_factory() as session:
        repositories = build_messaging_seed_repositories(session)

        await repositories.user_repository.add(
            User(
                id=setup.user_id,
                credential=Credential(
                    email=Email(user_email),
                    password_hash=PasswordHash("hash"),
                ),
                role=UserRole.CUSTOMER,
            ),
        )
        await repositories.account_balance_repository.save(
            AccountBalance(
                user_id=setup.user_id,
                available=Money(reserved_balance),
                reservations=[CreditReservation(job_id=setup.job_id, amount=Money(reservation_amount))],
            )
        )
        await repositories.billing_transaction_repository.add(
            BillingTransaction(
                id=TransactionId(uuid4()),
                user_id=setup.user_id,
                amount=Money(reservation_amount),
                transaction_type=TransactionType.RESERVATION,
                related_job_id=setup.job_id,
            )
        )
        await repositories.media_repository.add(
            MediaAsset(
                id=setup.media_asset_id,
                owner_id=setup.user_id,
                media_type=MediaType.AUDIO,
                location=FileLocation("/tmp/audio.wav"),
            ),
        )
        await repositories.model_repository.save(
            ModelProfile(
                id=setup.model_id,
                name=model_name,
                capabilities=[Capability.TRANSCRIPTION],
                pricing_rules=[PricingRule(Capability.TRANSCRIPTION, Money(Decimal("1")))],
            ),
        )

        job = ProcessingJob(
            id=setup.job_id,
            user_id=setup.user_id,
            media_asset_id=setup.media_asset_id,
            model_id=setup.model_id,
            job_type=JobType.TRANSCRIPTION,
            estimated_cost=Money(reservation_amount),
        )
        job.queue()
        await repositories.processing_repository.add(job)
        await session.commit()

    return setup


async def load_messaging_assertion_state(
    session_factory: async_sessionmaker[AsyncSession],
    setup: TranscriptionJobSetup,
) -> MessagingAssertionState:
    async with session_factory() as session:
        repositories = build_messaging_assertion_repositories(session)
        return MessagingAssertionState(
            job=await repositories.processing_repository.get_by_id(setup.job_id),
            balance=await repositories.account_balance_repository.get_by_user_id(setup.user_id),
            transactions=await repositories.billing_transaction_repository.list_by_user_id(setup.user_id),
        )


def build_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    processor: FakeProcessor,
    artifact_store: ResultArtifactStore,
) -> ProcessingWorker:
    return ProcessingWorker(
        session_factory,
        build_test_messaging_config(),
        processor=processor,
        artifact_store=artifact_store,
    )


def test_job_submitted_message_roundtrip() -> None:
    event = TranscriptionJobSubmitted(job_id=JobId(UUID("00000000-0000-0000-0000-000000000123")))

    payload = JobSubmittedMessage.from_event(event)

    assert payload is not None
    restored_payload = JobSubmittedMessage.from_body(payload.to_body())
    assert restored_payload == payload
    assert restored_payload.job_type == "transcription"


@pytest.mark.asyncio
async def test_worker_processes_job_and_confirms_reservation(db_context: DBContext, tmp_path: Path) -> None:
    session_factory = db_context.session_factory
    artifact_store = ResultArtifactStore(tmp_path / "results")
    fake_processor = FakeProcessor(
        result=JobExecutionResult(
            result_type="transcription",
            artifact_extension=".json",
            artifact_payload={
                "text": "real transcription result",
                "speaker_count": 2,
            },
            history_payload={
                "model_name": "openai/whisper-large-v3-turbo",
                "speaker_count": 2,
            },
        )
    )
    setup = await seed_transcription_job(
        session_factory,
        user_email="worker-test@grotesk.local",
        model_name="worker-model",
    )
    worker = build_worker(session_factory, processor=fake_processor, artifact_store=artifact_store)
    payload = JobSubmittedMessage(
        event_name="TranscriptionJobSubmitted",
        job_id=setup.job_id.value,
        job_type="transcription",
        submitted_at="2026-01-01T12:00:00+00:00",
    )

    await worker.process_message(payload)

    state = await load_messaging_assertion_state(session_factory, setup)

    assert state.job is not None
    assert state.job.status.value == "completed"
    assert state.job.result_ref is not None
    assert [record.status for record in state.job.history] == [
        ProcessingStatus.QUEUED,
        ProcessingStatus.RUNNING,
        ProcessingStatus.COMPLETED,
    ]
    assert "test-worker" in state.job.history[-1].message
    assert "transcription" in state.job.history[-1].message
    assert state.balance is not None
    assert state.balance.available.amount == Decimal("90")
    assert len(state.balance.reservations) == 1
    assert state.balance.reservations[0].is_confirmed is True
    assert {transaction.transaction_type for transaction in state.transactions} == {
        TransactionType.CHARGE,
        TransactionType.RESERVATION,
    }
    assert list((tmp_path / "results" / "transcription").glob("*.json"))


@pytest.mark.asyncio
async def test_worker_refunds_reservation_on_failure(db_context: DBContext, tmp_path: Path) -> None:
    session_factory = db_context.session_factory
    setup = await seed_transcription_job(
        session_factory,
        user_email="worker-refund@grotesk.local",
        model_name="openai/whisper-large-v3-turbo",
    )
    worker = build_worker(
        session_factory,
        processor=FakeProcessor(error=RuntimeError("gpu inference failed")),
        artifact_store=ResultArtifactStore(tmp_path / "results"),
    )

    with pytest.raises(RuntimeError, match="gpu inference failed"):
        await worker.process_message(
            JobSubmittedMessage(
                event_name="TranscriptionJobSubmitted",
                job_id=setup.job_id.value,
                job_type="transcription",
                submitted_at="2026-01-01T12:00:00+00:00",
            )
        )

    state = await load_messaging_assertion_state(session_factory, setup)

    assert state.job is not None
    assert state.job.status == ProcessingStatus.FAILED
    assert [record.status for record in state.job.history] == [
        ProcessingStatus.QUEUED,
        ProcessingStatus.RUNNING,
        ProcessingStatus.FAILED,
    ]
    assert state.balance is not None
    assert state.balance.available.amount == Decimal("100")
    assert state.balance.reservations == []
    assert {transaction.transaction_type for transaction in state.transactions} == {
        TransactionType.REFUND,
        TransactionType.RESERVATION,
    }


@pytest.mark.asyncio
async def test_processing_job_repository_persists_video_payload(db_context: DBContext) -> None:
    session_factory = db_context.session_factory
    user_id = UserId(uuid4())
    media_asset_id = MediaAssetId(uuid4())
    model_id = ModelId(uuid4())
    job_id = JobId(uuid4())

    async with session_factory() as session:
        repositories = build_messaging_seed_repositories(session)
        job = ProcessingJob(
            id=job_id,
            user_id=user_id,
            media_asset_id=media_asset_id,
            model_id=model_id,
            job_type=JobType.VIDEO_EDITING,
            estimated_cost=Money(Decimal("50")),
            prompt_text="Replace the speaker outfit with a red jacket.",
            operations=[
                TimelineOperation(
                    start_second=5,
                    end_second=9,
                    prompt="Change the jacket color to red.",
                    reference_asset_id=MediaAssetId(uuid4()),
                )
            ],
        )
        job.queue()
        await repositories.processing_repository.add(job)
        await session.commit()

    async with session_factory() as session:
        repositories = build_messaging_assertion_repositories(session)
        restored_job = await repositories.processing_repository.get_by_id(job_id)

        assert restored_job is not None
        assert restored_job.prompt_text == "Replace the speaker outfit with a red jacket."
        assert len(restored_job.operations) == 1
        assert restored_job.operations[0].prompt == "Change the jacket color to red."
        assert restored_job.operations[0].reference_asset_id is not None


@pytest.mark.asyncio
async def test_cancel_processing_job_marks_status_and_refunds_balance(db_context: DBContext) -> None:
    setup = await seed_transcription_job(
        db_context.session_factory,
        user_email="worker-cancel@grotesk.local",
        model_name="openai/whisper-large-v3-turbo",
    )

    async with db_context.session_factory() as session:
        application = build_application(session)
        await application.cancel_processing_job(CancelProcessingJob(job_id=setup.job_id, user_id=setup.user_id))

    state = await load_messaging_assertion_state(db_context.session_factory, setup)

    assert state.job is not None
    assert state.job.status == ProcessingStatus.CANCELED
    assert [record.status for record in state.job.history] == [
        ProcessingStatus.QUEUED,
        ProcessingStatus.CANCELED,
    ]
    assert state.balance is not None
    assert state.balance.available.amount == Decimal("100")
    assert state.balance.reservations == []
    assert {transaction.transaction_type for transaction in state.transactions} == {
        TransactionType.REFUND,
        TransactionType.RESERVATION,
    }
