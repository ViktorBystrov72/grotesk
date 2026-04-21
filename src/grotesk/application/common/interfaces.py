from typing import Protocol

from grotesk.domain.common.event import Event


class UnitOfWork(Protocol):
    async def commit(self) -> None:
        raise NotImplementedError

    async def rollback(self) -> None:
        raise NotImplementedError


class EventPublisher(Protocol):
    async def publish(self, events: list[Event]) -> None:
        raise NotImplementedError
