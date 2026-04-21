from abc import ABC, abstractmethod
from typing import Generic, TypeVar

CommandResultT = TypeVar("CommandResultT")
CommandT = TypeVar("CommandT")


class Command(Generic[CommandResultT], ABC):
    """Marker base class for commands."""


class CommandHandler(Generic[CommandT, CommandResultT], ABC):
    @abstractmethod
    async def __call__(self, command: CommandT) -> CommandResultT:
        raise NotImplementedError
