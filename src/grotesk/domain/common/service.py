from abc import ABC

from grotesk.domain.common.event import Event


class DomainService(ABC):
    """Base class for domain services that accumulate events."""

    def __init__(self) -> None:
        self._events: list[Event] = []

    def record_event(self, event: Event) -> None:
        self._events.append(event)

    def pull_events(self) -> list[Event]:
        events = self._events.copy()
        self._events.clear()
        return events
