from grotesk.domain.billing.events import CreditsReserved, TopUpApproved
from grotesk.domain.billing.interfaces import AccountBalanceRepository, TopUpRequestRepository
from grotesk.domain.billing.model import CreditReservation, TopUpRequestId
from grotesk.domain.common.primitives import Money
from grotesk.domain.common.service import DomainService
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.processing.model import JobId


class BillingService(DomainService):
    def __init__(
        self,
        account_balance_repository: AccountBalanceRepository,
        top_up_request_repository: TopUpRequestRepository,
    ) -> None:
        super().__init__()
        self._account_balance_repository = account_balance_repository
        self._top_up_request_repository = top_up_request_repository

    async def reserve_credits(self, user_id: UserId, job_id: JobId, amount: Money) -> None:
        account_balance = await self._account_balance_repository.get_by_user_id(user_id)
        if account_balance is None:
            raise ValueError("Account balance does not exist.")

        account_balance.reserve(CreditReservation(job_id=job_id, amount=amount))
        await self._account_balance_repository.save(account_balance)
        self.record_event(CreditsReserved(user_id=user_id, job_id=job_id, amount=amount))

    async def approve_top_up(self, request_id: TopUpRequestId) -> None:
        request = await self._top_up_request_repository.get_by_id(request_id)
        if request is None:
            raise ValueError("Top-up request does not exist.")

        account_balance = await self._account_balance_repository.get_by_user_id(request.user_id)
        if account_balance is None:
            raise ValueError("Account balance does not exist.")

        request.approve()
        account_balance.top_up(request.amount)

        await self._account_balance_repository.save(account_balance)
        self.record_event(
            TopUpApproved(
                request_id=request.id,
                user_id=request.user_id,
                amount=request.amount,
            ),
        )
