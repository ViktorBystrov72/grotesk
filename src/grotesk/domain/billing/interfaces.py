from typing import Protocol

from grotesk.domain.billing.model import AccountBalance, TopUpRequest, TopUpRequestId
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
