from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from grotesk.domain.common.value_object import ValueObject


@dataclass(frozen=True)
class Money(ValueObject):
    amount: Decimal
    currency: str = "CREDIT"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise ValueError(f"Money amount must be Decimal, got {type(self.amount).__name__}")
        if self.amount < Decimal("0"):
            raise ValueError("Money amount must be non-negative.")


@dataclass(frozen=True)
class FileLocation(ValueObject):
    storage_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.storage_key, str):
            raise ValueError(f"Storage key must be str, got {type(self.storage_key).__name__}")
        if not self.storage_key:
            raise ValueError("Storage key cannot be empty.")


@dataclass(frozen=True)
class TimestampRange(ValueObject):
    start_second: int
    end_second: int

    def __post_init__(self) -> None:
        if not isinstance(self.start_second, int) or not isinstance(self.end_second, int):
            raise ValueError("Timestamp bounds must be integers.")
        if self.start_second < 0:
            raise ValueError("Start second must be non-negative.")
        if self.end_second <= self.start_second:
            raise ValueError("End second must be greater than start second.")


@dataclass(frozen=True)
class EntityId(ValueObject):
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValueError(f"EntityId value must be UUID, got {type(self.value).__name__}")
