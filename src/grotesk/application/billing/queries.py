from dataclasses import dataclass

from grotesk.application.billing.dto import BillingTransactionDTO
from grotesk.application.common.query import Query, QueryHandler
from grotesk.domain.billing.interfaces import AccountBalanceRepository, BillingTransactionRepository
from grotesk.domain.identity_access.model import UserId


@dataclass(frozen=True)
class GetUserBalance(Query[str]):
    user_id: UserId


class GetUserBalanceHandler(QueryHandler[GetUserBalance, str]):
    def __init__(self, account_balance_repository: AccountBalanceRepository) -> None:
        self._account_balance_repository = account_balance_repository

    async def __call__(self, query: GetUserBalance) -> str:
        balance = await self._account_balance_repository.get_by_user_id(query.user_id)
        if balance is None:
            raise ValueError("Balance not found.")
        return str(balance.available.amount)


@dataclass(frozen=True)
class GetUserTransactionHistory(Query[list[BillingTransactionDTO]]):
    user_id: UserId


class GetUserTransactionHistoryHandler(QueryHandler[GetUserTransactionHistory, list[BillingTransactionDTO]]):
    def __init__(self, billing_transaction_repository: BillingTransactionRepository) -> None:
        self._billing_transaction_repository = billing_transaction_repository

    async def __call__(self, query: GetUserTransactionHistory) -> list[BillingTransactionDTO]:
        transactions = await self._billing_transaction_repository.list_by_user_id(query.user_id)
        return [
            BillingTransactionDTO(
                transaction_type=transaction.transaction_type,
                amount=str(transaction.amount.amount),
                currency=transaction.amount.currency,
                created_at=transaction.created_at,
                related_job_id=transaction.related_job_id,
            )
            for transaction in transactions
        ]
