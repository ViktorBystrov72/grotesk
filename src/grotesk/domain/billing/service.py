from decimal import Decimal
from uuid import uuid4

from grotesk.domain.billing.events import CreditsReserved, TopUpApproved
from grotesk.domain.billing.interfaces import (
    AccountBalanceRepository,
    BillingTransactionRepository,
    TopUpRequestRepository,
)
from grotesk.domain.billing.model import (
    AccountBalance,
    BillingTransaction,
    CreditReservation,
    TopUpRequestId,
    TransactionId,
    TransactionType,
)
from grotesk.domain.common.primitives import Money
from grotesk.domain.common.service import DomainService
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.processing.model import JobId


class BillingService(DomainService):
    def __init__(
        self,
        account_balance_repository: AccountBalanceRepository,
        top_up_request_repository: TopUpRequestRepository,
        billing_transaction_repository: BillingTransactionRepository,
    ) -> None:
        super().__init__()
        self._account_balance_repository = account_balance_repository
        self._top_up_request_repository = top_up_request_repository
        self._billing_transaction_repository = billing_transaction_repository

    async def create_account(self, user_id: UserId, currency: str = "CREDIT") -> AccountBalance:
        account_balance = AccountBalance(user_id=user_id, available=Money(Decimal("0"), currency))
        await self._account_balance_repository.save(account_balance)
        return account_balance

    async def reserve_credits(self, user_id: UserId, job_id: JobId, amount: Money) -> None:
        account_balance = await self._account_balance_repository.get_by_user_id(user_id)
        if account_balance is None:
            raise ValueError("Account balance does not exist.")

        account_balance.reserve(CreditReservation(job_id=job_id, amount=amount))
        await self._account_balance_repository.save(account_balance)
        await self._billing_transaction_repository.add(
            BillingTransaction(
                id=TransactionId(uuid4()),
                user_id=user_id,
                amount=amount,
                transaction_type=TransactionType.RESERVATION,
                related_job_id=job_id,
            ),
        )
        self.record_event(CreditsReserved(user_id=user_id, job_id=job_id, amount=amount))

    async def confirm_reservation(self, user_id: UserId, job_id: JobId) -> None:
        account_balance = await self._account_balance_repository.get_by_user_id(user_id)
        if account_balance is None:
            raise ValueError("Account balance does not exist.")

        confirmed_amount = account_balance.confirm_reservation(job_id)
        if confirmed_amount is None:
            return

        await self._account_balance_repository.save(account_balance)
        await self._billing_transaction_repository.add(
            BillingTransaction(
                id=TransactionId(uuid4()),
                user_id=user_id,
                amount=confirmed_amount,
                transaction_type=TransactionType.CHARGE,
                related_job_id=job_id,
            ),
        )

    async def release_reservation(self, user_id: UserId, job_id: JobId) -> None:
        account_balance = await self._account_balance_repository.get_by_user_id(user_id)
        if account_balance is None:
            raise ValueError("Account balance does not exist.")

        released_amount = account_balance.release_reservation(job_id)
        if released_amount is None:
            return

        await self._account_balance_repository.save(account_balance)
        await self._billing_transaction_repository.add(
            BillingTransaction(
                id=TransactionId(uuid4()),
                user_id=user_id,
                amount=released_amount,
                transaction_type=TransactionType.REFUND,
                related_job_id=job_id,
            ),
        )

    async def top_up_balance(self, user_id: UserId, amount: Money) -> None:
        account_balance = await self._account_balance_repository.get_by_user_id(user_id)
        if account_balance is None:
            raise ValueError("Account balance does not exist.")

        account_balance.top_up(amount)
        await self._account_balance_repository.save(account_balance)
        await self._billing_transaction_repository.add(
            BillingTransaction(
                id=TransactionId(uuid4()),
                user_id=user_id,
                amount=amount,
                transaction_type=TransactionType.TOP_UP,
            ),
        )

    async def debit_balance(self, user_id: UserId, amount: Money, related_job_id: JobId | None = None) -> None:
        account_balance = await self._account_balance_repository.get_by_user_id(user_id)
        if account_balance is None:
            raise ValueError("Account balance does not exist.")

        account_balance.debit(amount)
        await self._account_balance_repository.save(account_balance)
        await self._billing_transaction_repository.add(
            BillingTransaction(
                id=TransactionId(uuid4()),
                user_id=user_id,
                amount=amount,
                transaction_type=TransactionType.CHARGE,
                related_job_id=related_job_id,
            ),
        )

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
        await self._top_up_request_repository.save(request)
        await self._billing_transaction_repository.add(
            BillingTransaction(
                id=TransactionId(uuid4()),
                user_id=request.user_id,
                amount=request.amount,
                transaction_type=TransactionType.TOP_UP,
            ),
        )
        self.record_event(
            TopUpApproved(
                request_id=request.id,
                user_id=request.user_id,
                amount=request.amount,
            ),
        )
