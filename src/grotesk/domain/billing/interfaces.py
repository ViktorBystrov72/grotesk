from typing import Protocol

from grotesk.domain.billing.model import (
    AccountBalance,
    BillingTransaction,
    TopUpRequest,
    TopUpRequestId,
    TransactionId,
)
from grotesk.domain.identity_access.model import UserId


class AccountBalanceRepository(Protocol):
    async def get_by_user_id(self, user_id: UserId) -> AccountBalance | None:
        raise NotImplementedError

    async def save(self, account_balance: AccountBalance) -> None:
        raise NotImplementedError


class TopUpRequestRepository(Protocol):
    async def add(self, request: TopUpRequest) -> None:
        raise NotImplementedError

    async def get_by_id(self, request_id: TopUpRequestId) -> TopUpRequest | None:
        raise NotImplementedError

    async def save(self, request: TopUpRequest) -> None:
        raise NotImplementedError


class BillingTransactionRepository(Protocol):
    async def add(self, transaction: BillingTransaction) -> None:
        raise NotImplementedError

    async def get_by_id(self, transaction_id: TransactionId) -> BillingTransaction | None:
        raise NotImplementedError

    async def list_by_user_id(self, user_id: UserId) -> list[BillingTransaction]:
        raise NotImplementedError
