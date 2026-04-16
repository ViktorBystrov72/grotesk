from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Event:
    """Base class for domain events."""

    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC), kw_only=True)
