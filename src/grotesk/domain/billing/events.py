from dataclasses import dataclass

from grotesk.domain.billing.model import TopUpRequestId
from grotesk.domain.common.event import Event
from grotesk.domain.common.primitives import Money
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.processing.model import JobId


@dataclass(frozen=True)
class CreditsReserved(Event):
    user_id: UserId
    job_id: JobId
    amount: Money


@dataclass(frozen=True)
class TopUpApproved(Event):
    request_id: TopUpRequestId
    user_id: UserId
    amount: Money
