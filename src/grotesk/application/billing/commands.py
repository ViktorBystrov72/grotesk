from dataclasses import dataclass

from grotesk.application.common.command import Command, CommandHandler
from grotesk.application.common.interfaces import EventPublisher, UnitOfWork
from grotesk.domain.billing.model import TopUpRequestId
from grotesk.domain.billing.service import BillingService


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
