import asyncio
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from grotesk.application.billing.commands import TopUpBalance
from grotesk.application.identity_access.commands import RegisterUser
from grotesk.domain.catalog.model import Capability, ModelId, ModelProfile, PricingRule
from grotesk.domain.common.primitives import Money
from grotesk.domain.identity_access.model import Email, UserId, UserRole
from grotesk.infrastructure.db.base import Base
from grotesk.infrastructure.db.models.entities import ModelProfileModel
from grotesk.infrastructure.db.repositories.billing import AccountBalanceRepositoryImpl
from grotesk.infrastructure.db.repositories.catalog import ModelCatalogRepositoryImpl
from grotesk.infrastructure.db.repositories.user import UserRepositoryImpl
from grotesk.infrastructure.db.schema_compat import ensure_processing_jobs_video_columns
from grotesk.infrastructure.ml.config import MLConfig
from grotesk.main.bootstrap import build_application


async def create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def wait_for_database(engine: AsyncEngine, retries: int = 20, delay_seconds: float = 1.5) -> None:
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return
        except Exception as error:  # pragma: no cover - startup resilience
            last_error = error
            await asyncio.sleep(delay_seconds)

    if last_error is not None:
        raise last_error


async def seed_demo_data(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        app = build_application(session)
        ml_config = MLConfig.from_env()
        user_repository = UserRepositoryImpl(session)
        account_balance_repository = AccountBalanceRepositoryImpl(session)
        model_catalog_repository = ModelCatalogRepositoryImpl(session)

        demo_user = await user_repository.get_by_email(Email("demo@grotesk.local"))
        if demo_user is None:
            demo_user_id = UserId(uuid4())
            await app.register_user(
                RegisterUser(
                    user_id=demo_user_id,
                    email="demo@grotesk.local",
                    password_hash="demo-password-hash",
                    role=UserRole.CUSTOMER,
                ),
            )
            demo_user = await user_repository.get_by_id(demo_user_id)

        demo_admin = await user_repository.get_by_email(Email("admin@grotesk.local"))
        if demo_admin is None:
            demo_admin_id = UserId(uuid4())
            await app.register_user(
                RegisterUser(
                    user_id=demo_admin_id,
                    email="admin@grotesk.local",
                    password_hash="admin-password-hash",
                    role=UserRole.ADMIN,
                ),
            )
            demo_admin = await user_repository.get_by_id(demo_admin_id)

        if demo_user is not None:
            demo_user_balance = await account_balance_repository.get_by_user_id(demo_user.id)
            if demo_user_balance is not None and demo_user_balance.available.amount == Decimal("0"):
                await app.top_up_balance(TopUpBalance(user_id=demo_user.id, amount=Money(Decimal("100"))))

        if demo_admin is not None:
            demo_admin_balance = await account_balance_repository.get_by_user_id(demo_admin.id)
            if demo_admin_balance is not None and demo_admin_balance.available.amount == Decimal("0"):
                await app.top_up_balance(TopUpBalance(user_id=demo_admin.id, amount=Money(Decimal("500"))))

        default_models = [
            ModelProfile(
                id=ModelId(uuid4()),
                name=ml_config.audio_model_id,
                capabilities=[Capability.TRANSCRIPTION, Capability.DIARIZATION],
                pricing_rules=[
                    PricingRule(Capability.TRANSCRIPTION, Money(Decimal("3"))),
                    PricingRule(Capability.DIARIZATION, Money(Decimal("2"))),
                ],
            ),
            ModelProfile(
                id=ModelId(uuid4()),
                name=ml_config.video_model_id,
                capabilities=[Capability.VIDEO_EDITING, Capability.IMAGE_REPLACEMENT, Capability.BODY_RESHAPING],
                pricing_rules=[
                    PricingRule(Capability.VIDEO_EDITING, Money(Decimal("10"))),
                    PricingRule(Capability.IMAGE_REPLACEMENT, Money(Decimal("7"))),
                    PricingRule(Capability.BODY_RESHAPING, Money(Decimal("6"))),
                ],
            ),
        ]

        existing_names = set((await session.execute(select(ModelProfileModel.name))).scalars().all())
        for candidate in default_models:
            if candidate.name not in existing_names:
                await model_catalog_repository.save(candidate)
                await session.commit()
                existing_names.add(candidate.name)


async def initialize_database(engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await wait_for_database(engine)
    await create_schema(engine)
    await ensure_processing_jobs_video_columns(engine)
    await seed_demo_data(session_factory)
