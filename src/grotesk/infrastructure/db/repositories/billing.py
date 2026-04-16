from sqlalchemy import select
from sqlalchemy.orm import selectinload

from grotesk.domain.billing.interfaces import (
    AccountBalanceRepository,
    BillingTransactionRepository,
    TopUpRequestRepository,
)
from grotesk.domain.billing.model import (
    AccountBalance,
    BillingTransaction,
    TopUpRequest,
    TopUpRequestId,
    TransactionId,
)
from grotesk.domain.identity_access.model import UserId
from grotesk.infrastructure.db.mappers import (
    account_balance_to_domain,
    billing_transaction_to_domain,
    top_up_request_to_domain,
)
from grotesk.infrastructure.db.models.entities import (
    AccountBalanceModel,
    BillingTransactionModel,
    CreditReservationModel,
    TopUpRequestModel,
)
from grotesk.infrastructure.db.repositories.base import SQLAlchemyRepository


class AccountBalanceRepositoryImpl(SQLAlchemyRepository, AccountBalanceRepository):
    async def get_by_user_id(self, user_id: UserId) -> AccountBalance | None:
        model = await self._session.scalar(
            select(AccountBalanceModel)
            .options(selectinload(AccountBalanceModel.reservations))
            .where(AccountBalanceModel.user_id == user_id.value),
        )
        if model is None:
            return None
        return account_balance_to_domain(model)

    async def save(self, account_balance: AccountBalance) -> None:
        model = await self._session.scalar(
            select(AccountBalanceModel)
            .options(selectinload(AccountBalanceModel.reservations))
            .where(AccountBalanceModel.user_id == account_balance.user_id.value),
        )
        if model is None:
            model = AccountBalanceModel(user_id=account_balance.user_id.value)
            self._session.add(model)

        model.available_amount = account_balance.available.amount
        model.currency = account_balance.available.currency
        model.reservations = [
            CreditReservationModel(
                user_id=account_balance.user_id.value,
                job_id=reservation.job_id.value,
                amount=reservation.amount.amount,
                currency=reservation.amount.currency,
                is_confirmed=reservation.is_confirmed,
            )
            for reservation in account_balance.reservations
        ]
        await self._session.flush()


class TopUpRequestRepositoryImpl(SQLAlchemyRepository, TopUpRequestRepository):
    async def add(self, request: TopUpRequest) -> None:
        self._session.add(
            TopUpRequestModel(
                id=request.id.value,
                user_id=request.user_id.value,
                amount=request.amount.amount,
                currency=request.amount.currency,
                status=request.status,
            ),
        )
        await self._session.flush()

    async def get_by_id(self, request_id: TopUpRequestId) -> TopUpRequest | None:
        model = await self._session.get(TopUpRequestModel, request_id.value)
        if model is None:
            return None
        return top_up_request_to_domain(model)

    async def save(self, request: TopUpRequest) -> None:
        model = await self._session.get(TopUpRequestModel, request.id.value)
        if model is None:
            model = TopUpRequestModel(
                id=request.id.value,
                user_id=request.user_id.value,
                amount=request.amount.amount,
                currency=request.amount.currency,
                status=request.status,
            )
            self._session.add(model)
        else:
            model.user_id = request.user_id.value
            model.amount = request.amount.amount
            model.currency = request.amount.currency
            model.status = request.status
        await self._session.flush()


class BillingTransactionRepositoryImpl(SQLAlchemyRepository, BillingTransactionRepository):
    async def add(self, transaction: BillingTransaction) -> None:
        self._session.add(
            BillingTransactionModel(
                id=transaction.id.value,
                user_id=transaction.user_id.value,
                amount=transaction.amount.amount,
                currency=transaction.amount.currency,
                transaction_type=transaction.transaction_type,
                related_job_id=transaction.related_job_id.value if transaction.related_job_id else None,
            ),
        )
        await self._session.flush()

    async def get_by_id(self, transaction_id: TransactionId) -> BillingTransaction | None:
        model = await self._session.get(BillingTransactionModel, transaction_id.value)
        if model is None:
            return None
        return billing_transaction_to_domain(model)

    async def list_by_user_id(self, user_id: UserId) -> list[BillingTransaction]:
        models = list(
            await self._session.scalars(
                select(BillingTransactionModel)
                .where(BillingTransactionModel.user_id == user_id.value)
                .order_by(BillingTransactionModel.created_at.desc()),
            ),
        )
        return [billing_transaction_to_domain(model) for model in models]
