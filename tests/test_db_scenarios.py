from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from grotesk.application.billing.commands import DebitBalance, TopUpBalance
from grotesk.application.billing.queries import GetUserTransactionHistory
from grotesk.application.identity_access.commands import RegisterUser
from grotesk.application.processing.commands import SubmitTranscriptionJob, SubmitVideoEditingJob
from grotesk.application.processing.queries import GetUserJobHistory
from grotesk.domain.billing.model import TransactionType
from grotesk.domain.catalog.model import Capability, ModelId, ModelProfile, PricingRule
from grotesk.domain.common.primitives import FileLocation, Money
from grotesk.domain.identity_access.model import Email, UserId
from grotesk.domain.media_ingestion.model import MediaAsset, MediaAssetId, MediaType
from grotesk.domain.processing.model import JobId, JobType, ProcessingStatus, TimelineOperation
from grotesk.infrastructure.db.init_data import initialize_database
from grotesk.infrastructure.db.models.entities import ModelProfileModel, UserModel
from grotesk.main.bootstrap import build_application
from tests.support import (
    DBContext,
    build_messaging_assertion_repositories,
    build_messaging_seed_repositories,
    build_user_balance_repositories,
)


async def seed_user_media_and_model(
    db_context: DBContext,
    *,
    email: str,
    balance_amount: Decimal,
    media_type: MediaType = MediaType.AUDIO,
    capability: Capability = Capability.TRANSCRIPTION,
) -> tuple[UserId, MediaAssetId, ModelId]:
    user_id = UserId(uuid4())
    media_asset_id = MediaAssetId(uuid4())
    model_id = ModelId(uuid4())

    async with db_context.session_factory() as session:
        app = build_application(session)
        await app.register_user(RegisterUser(user_id=user_id, email=email, password_hash="hash"))
        if balance_amount:
            await app.top_up_balance(TopUpBalance(user_id=user_id, amount=Money(balance_amount)))

        repositories = build_messaging_seed_repositories(session)
        await repositories.media_repository.add(
            MediaAsset(
                id=media_asset_id,
                owner_id=user_id,
                media_type=media_type,
                location=FileLocation(f"/tmp/{media_type.value}.bin"),
            )
        )
        await repositories.model_repository.save(
            ModelProfile(
                id=model_id,
                name=f"test-{capability.value}-model",
                capabilities=[capability],
                pricing_rules=[PricingRule(capability, Money(Decimal("1")))],
            )
        )
        await session.commit()

    return user_id, media_asset_id, model_id


@pytest.mark.asyncio
async def test_register_user_creates_balance(db_context: DBContext) -> None:
    session_factory = db_context.session_factory

    async with session_factory() as session:
        app = build_application(session)
        user_id = UserId(uuid4())

        await app.register_user(
            RegisterUser(
                user_id=user_id,
                email="user1@grotesk.local",
                password_hash="hash-1",
            ),
        )

        repositories = build_user_balance_repositories(session)

        user = await repositories.user_repository.get_by_id(user_id)
        balance = await repositories.balance_repository.get_by_user_id(user_id)

        assert user is not None
        assert balance is not None
        assert user.credential.email == Email("user1@grotesk.local")
        assert balance.available.amount == Decimal("0")


@pytest.mark.asyncio
async def test_top_up_and_debit_persist_transactions(db_context: DBContext) -> None:
    session_factory = db_context.session_factory

    async with session_factory() as session:
        app = build_application(session)
        user_id = UserId(uuid4())

        await app.register_user(
            RegisterUser(
                user_id=user_id,
                email="billing@grotesk.local",
                password_hash="hash-2",
            ),
        )
        await app.top_up_balance(TopUpBalance(user_id=user_id, amount=Money(Decimal("50"))))
        await app.debit_balance(DebitBalance(user_id=user_id, amount=Money(Decimal("20"))))

        repositories = build_user_balance_repositories(session)
        balance = await repositories.balance_repository.get_by_user_id(user_id)
        history = await app.get_user_transaction_history(GetUserTransactionHistory(user_id=user_id))

        assert balance is not None
        assert balance.available.amount == Decimal("30")
        assert len(history) == 2
        amounts = {h.amount for h in history}
        assert amounts == {"20.00", "50.00"}


@pytest.mark.asyncio
async def test_submit_transcription_job_reserves_credits_and_records_history(db_context: DBContext) -> None:
    user_id, media_asset_id, model_id = await seed_user_media_and_model(
        db_context,
        email="submit-transcription@grotesk.local",
        balance_amount=Decimal("30"),
    )
    job_id = JobId(uuid4())

    async with db_context.session_factory() as session:
        app = build_application(session)
        await app.submit_transcription_job(
            SubmitTranscriptionJob(
                job_id=job_id,
                user_id=user_id,
                media_asset_id=media_asset_id,
                model_id=model_id,
                estimated_cost=Money(Decimal("10")),
            )
        )

    async with db_context.session_factory() as session:
        repositories = build_messaging_assertion_repositories(session)
        balance = await repositories.account_balance_repository.get_by_user_id(user_id)
        job = await repositories.processing_repository.get_by_id(job_id)
        transactions = await repositories.billing_transaction_repository.list_by_user_id(user_id)
        app = build_application(session)
        jobs = await app.get_user_job_history(GetUserJobHistory(user_id=user_id))

        assert balance is not None
        assert balance.available.amount == Decimal("20")
        assert len(balance.reservations) == 1
        assert balance.reservations[0].job_id == job_id
        assert balance.reservations[0].is_confirmed is False
        assert job is not None
        assert job.status == ProcessingStatus.QUEUED
        assert [record.status for record in job.history] == [ProcessingStatus.QUEUED]
        assert any(transaction.transaction_type == TransactionType.RESERVATION for transaction in transactions)
        assert jobs[0].job_id == job_id
        assert jobs[0].job_type == JobType.TRANSCRIPTION


@pytest.mark.asyncio
async def test_submit_video_editing_job_persists_prompt_operations_and_reserves_credits(
    db_context: DBContext,
) -> None:
    user_id, media_asset_id, model_id = await seed_user_media_and_model(
        db_context,
        email="submit-video@grotesk.local",
        balance_amount=Decimal("100"),
        media_type=MediaType.VIDEO,
        capability=Capability.VIDEO_EDITING,
    )
    job_id = JobId(uuid4())

    async with db_context.session_factory() as session:
        app = build_application(session)
        await app.submit_video_edit_job(
            SubmitVideoEditingJob(
                job_id=job_id,
                user_id=user_id,
                media_asset_id=media_asset_id,
                model_id=model_id,
                estimated_cost=Money(Decimal("50")),
                prompt_text="Replace the background with a city street.",
                operations=[
                    TimelineOperation(
                        start_second=10,
                        end_second=20,
                        prompt="Make the background look like a city street.",
                    )
                ],
            )
        )

    async with db_context.session_factory() as session:
        repositories = build_messaging_assertion_repositories(session)
        balance = await repositories.account_balance_repository.get_by_user_id(user_id)
        job = await repositories.processing_repository.get_by_id(job_id)

        assert balance is not None
        assert balance.available.amount == Decimal("50")
        assert len(balance.reservations) == 1
        assert job is not None
        assert job.job_type == JobType.VIDEO_EDITING
        assert job.prompt_text == "Replace the background with a city street."
        assert len(job.operations) == 1
        assert job.operations[0].start_second == 10
        assert job.operations[0].end_second == 20


@pytest.mark.asyncio
async def test_submit_transcription_job_rejects_insufficient_balance_without_persisting_job(
    db_context: DBContext,
) -> None:
    user_id, media_asset_id, model_id = await seed_user_media_and_model(
        db_context,
        email="insufficient@grotesk.local",
        balance_amount=Decimal("5"),
    )
    job_id = JobId(uuid4())

    async with db_context.session_factory() as session:
        app = build_application(session)
        with pytest.raises(ValueError, match="Insufficient balance"):
            await app.submit_transcription_job(
                SubmitTranscriptionJob(
                    job_id=job_id,
                    user_id=user_id,
                    media_asset_id=media_asset_id,
                    model_id=model_id,
                    estimated_cost=Money(Decimal("10")),
                )
            )
        await session.rollback()

    async with db_context.session_factory() as session:
        repositories = build_messaging_assertion_repositories(session)
        balance = await repositories.account_balance_repository.get_by_user_id(user_id)
        job = await repositories.processing_repository.get_by_id(job_id)
        transactions = await repositories.billing_transaction_repository.list_by_user_id(user_id)

        assert balance is not None
        assert balance.available.amount == Decimal("5")
        assert balance.reservations == []
        assert job is None
        assert [transaction.transaction_type for transaction in transactions] == [TransactionType.TOP_UP]


@pytest.mark.asyncio
async def test_initialize_database_is_idempotent(db_context: DBContext) -> None:
    engine = db_context.engine
    session_factory = db_context.session_factory

    await initialize_database(engine, session_factory)
    await initialize_database(engine, session_factory)

    async with session_factory() as session:
        user_count = (await session.execute(select(UserModel.id))).scalars().all()
        model_count = (await session.execute(select(ModelProfileModel.id))).scalars().all()

        repositories = build_user_balance_repositories(session)

        demo_user = await repositories.user_repository.get_by_email(Email("demo@grotesk.local"))
        demo_admin = await repositories.user_repository.get_by_email(Email("admin@grotesk.local"))

        assert len(user_count) == 2
        assert len(model_count) == 2
        assert demo_user is not None
        assert demo_admin is not None

        demo_user_balance = await repositories.balance_repository.get_by_user_id(demo_user.id)
        demo_admin_balance = await repositories.balance_repository.get_by_user_id(demo_admin.id)

        assert demo_user_balance is not None
        assert demo_admin_balance is not None
        assert demo_user_balance.available.amount == Decimal("100")
        assert demo_admin_balance.available.amount == Decimal("500")
