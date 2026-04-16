from dataclasses import dataclass

from grotesk.application.common.command import Command, CommandHandler
from grotesk.application.common.interfaces import EventPublisher, UnitOfWork
from grotesk.domain.billing.model import TopUpRequestId
from grotesk.domain.billing.service import BillingService
from grotesk.domain.common.primitives import Money
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.processing.model import JobId


@dataclass(frozen=True)
class ApproveTopUp(Command[TopUpRequestId]):
    request_id: TopUpRequestId


class ApproveTopUpHandler(CommandHandler[ApproveTopUp, TopUpRequestId]):
    def __init__(
        self,
        billing_service: BillingService,
        publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._billing_service = billing_service
        self._publisher = publisher
        self._uow = uow

    async def __call__(self, command: ApproveTopUp) -> TopUpRequestId:
        await self._billing_service.approve_top_up(command.request_id)
        await self._publisher.publish(self._billing_service.pull_events())
        await self._uow.commit()
        return command.request_id


@dataclass(frozen=True)
class TopUpBalance(Command[UserId]):
    user_id: UserId
    amount: Money


class TopUpBalanceHandler(CommandHandler[TopUpBalance, UserId]):
    def __init__(self, billing_service: BillingService, publisher: EventPublisher, uow: UnitOfWork) -> None:
        self._billing_service = billing_service
        self._publisher = publisher
        self._uow = uow

    async def __call__(self, command: TopUpBalance) -> UserId:
        await self._billing_service.top_up_balance(command.user_id, command.amount)
        await self._publisher.publish(self._billing_service.pull_events())
        await self._uow.commit()
        return command.user_id


@dataclass(frozen=True)
class DebitBalance(Command[UserId]):
    user_id: UserId
    amount: Money
    related_job_id: JobId | None = None


class DebitBalanceHandler(CommandHandler[DebitBalance, UserId]):
    def __init__(self, billing_service: BillingService, publisher: EventPublisher, uow: UnitOfWork) -> None:
        self._billing_service = billing_service
        self._publisher = publisher
        self._uow = uow

    async def __call__(self, command: DebitBalance) -> UserId:
        await self._billing_service.debit_balance(command.user_id, command.amount, command.related_job_id)
        await self._publisher.publish(self._billing_service.pull_events())
        await self._uow.commit()
        return command.user_id
