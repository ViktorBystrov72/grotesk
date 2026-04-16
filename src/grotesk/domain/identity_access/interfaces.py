from typing import Protocol

from grotesk.domain.identity_access.model import Email, User, UserId


class UserRepository(Protocol):
    async def add(self, user: User) -> None:
        raise NotImplementedError

    async def get_by_id(self, user_id: UserId) -> User | None:
        raise NotImplementedError

    async def get_by_email(self, email: Email) -> User | None:
        raise NotImplementedError
