from abc import ABC, abstractmethod
from typing import Generic, TypeVar

QueryResultT = TypeVar("QueryResultT")
QueryT = TypeVar("QueryT")


class Query(Generic[QueryResultT], ABC):
    """Marker base class for queries."""


class QueryHandler(Generic[QueryT, QueryResultT], ABC):
    @abstractmethod
    async def __call__(self, query: QueryT) -> QueryResultT:
        raise NotImplementedError
