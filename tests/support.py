from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from grotesk.infrastructure.db.repositories.billing import (
    AccountBalanceRepositoryImpl,
    BillingTransactionRepositoryImpl,
)
from grotesk.infrastructure.db.repositories.catalog import ModelCatalogRepositoryImpl
from grotesk.infrastructure.db.repositories.media import MediaAssetRepositoryImpl
from grotesk.infrastructure.db.repositories.processing import ProcessingJobRepositoryImpl
from grotesk.infrastructure.db.repositories.user import UserRepositoryImpl
from grotesk.infrastructure.messaging.config import MessagingConfig


@dataclass(frozen=True)
class DBContext:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


@dataclass(frozen=True)
class UserBalanceRepositories:
    user_repository: UserRepositoryImpl
    balance_repository: AccountBalanceRepositoryImpl


@dataclass(frozen=True)
class MessagingSeedRepositories:
    account_balance_repository: AccountBalanceRepositoryImpl
    user_repository: UserRepositoryImpl
    media_repository: MediaAssetRepositoryImpl
    model_repository: ModelCatalogRepositoryImpl
    processing_repository: ProcessingJobRepositoryImpl


@dataclass(frozen=True)
class MessagingAssertionRepositories:
    account_balance_repository: AccountBalanceRepositoryImpl
    billing_transaction_repository: BillingTransactionRepositoryImpl
    processing_repository: ProcessingJobRepositoryImpl


def build_user_balance_repositories(session: AsyncSession) -> UserBalanceRepositories:
    return UserBalanceRepositories(
        user_repository=UserRepositoryImpl(session),
        balance_repository=AccountBalanceRepositoryImpl(session),
    )


def build_messaging_seed_repositories(session: AsyncSession) -> MessagingSeedRepositories:
    return MessagingSeedRepositories(
        account_balance_repository=AccountBalanceRepositoryImpl(session),
        user_repository=UserRepositoryImpl(session),
        media_repository=MediaAssetRepositoryImpl(session),
        model_repository=ModelCatalogRepositoryImpl(session),
        processing_repository=ProcessingJobRepositoryImpl(session),
    )


def build_messaging_assertion_repositories(session: AsyncSession) -> MessagingAssertionRepositories:
    return MessagingAssertionRepositories(
        account_balance_repository=AccountBalanceRepositoryImpl(session),
        billing_transaction_repository=BillingTransactionRepositoryImpl(session),
        processing_repository=ProcessingJobRepositoryImpl(session),
    )


def build_test_messaging_config() -> MessagingConfig:
    return MessagingConfig(
        backend="rabbitmq",
        amqp_url="amqp://guest:guest@localhost:5672/",
        queue_name="ml_tasks",
        prefetch_count=1,
        durable_queue=True,
        worker_id="test-worker",
        processing_delay_seconds=0,
    )
