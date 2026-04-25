from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from grotesk.application.billing.commands import DebitBalance, TopUpBalance
from grotesk.application.billing.queries import GetUserTransactionHistory
from grotesk.application.identity_access.commands import RegisterUser
from grotesk.domain.common.primitives import Money
from grotesk.domain.identity_access.model import Email, UserId
from grotesk.infrastructure.db.init_data import initialize_database
from grotesk.infrastructure.db.models.entities import ModelProfileModel, UserModel
from grotesk.main.bootstrap import build_application
from tests.support import DBContext, build_user_balance_repositories


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
