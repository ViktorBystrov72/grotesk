from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from grotesk.domain.common.entity import Entity
from grotesk.domain.common.primitives import EntityId, Money
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.processing.model import JobId


class TransactionType(StrEnum):
    TOP_UP = "top_up"
    RESERVATION = "reservation"
    CHARGE = "charge"
    REFUND = "refund"


class TopUpStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class TransactionId(EntityId):
    pass


@dataclass(frozen=True)
class TopUpRequestId(EntityId):
    pass


@dataclass
class BillingTransaction(Entity):
    id: TransactionId
    user_id: UserId
    amount: Money
    transaction_type: TransactionType
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    related_job_id: JobId | None = None


@dataclass
class CreditReservation(Entity):
    job_id: JobId
    amount: Money
    is_confirmed: bool = False

    def confirm(self) -> None:
        self.is_confirmed = True


@dataclass
class AccountBalance(Entity):
    user_id: UserId
    available: Money
    reservations: list[CreditReservation] = field(default_factory=list)

    def can_reserve(self, amount: Money) -> bool:
        return self.available.amount >= amount.amount

    def reserve(self, reservation: CreditReservation) -> None:
        if not self.can_reserve(reservation.amount):
            raise ValueError("Insufficient balance for reservation.")
        self.available = Money(self.available.amount - reservation.amount.amount, self.available.currency)
        self.reservations.append(reservation)

    def top_up(self, amount: Money) -> None:
        self.available = Money(self.available.amount + amount.amount, self.available.currency)

    def debit(self, amount: Money) -> None:
        if not self.can_reserve(amount):
            raise ValueError("Insufficient balance for debit.")
        self.available = Money(self.available.amount - amount.amount, self.available.currency)


@dataclass
class TopUpRequest(Entity):
    id: TopUpRequestId
    user_id: UserId
    amount: Money
    status: TopUpStatus = TopUpStatus.PENDING

    def approve(self) -> None:
        self.status = TopUpStatus.APPROVED

    def reject(self) -> None:
        self.status = TopUpStatus.REJECTED
