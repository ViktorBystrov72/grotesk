from dataclasses import dataclass

from grotesk.application.common.query import Query, QueryHandler
from grotesk.application.identity_access.dto import UserDTO
from grotesk.domain.identity_access.interfaces import UserRepository
from grotesk.domain.identity_access.model import Email, UserId


@dataclass(frozen=True)
class GetUserById(Query[UserDTO]):
    user_id: UserId


@dataclass(frozen=True)
class GetUserByEmail(Query[UserDTO]):
    email: str


class GetUserByEmailHandler(QueryHandler[GetUserByEmail, UserDTO]):
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def __call__(self, query: GetUserByEmail) -> UserDTO:
        user = await self._user_repository.get_by_email(Email(query.email))
        if user is None:
            raise ValueError("User does not exist.")

        return UserDTO(
            user_id=user.id,
            email=user.credential.email.value,
            password_hash=user.credential.password_hash.value,
            role=user.role,
            is_active=user.is_active,
        )


class GetUserByIdHandler(QueryHandler[GetUserById, UserDTO]):
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def __call__(self, query: GetUserById) -> UserDTO:
        user = await self._user_repository.get_by_id(query.user_id)
        if user is None:
            raise ValueError("User does not exist.")

        return UserDTO(
            user_id=user.id,
            email=user.credential.email.value,
            password_hash=user.credential.password_hash.value,
            role=user.role,
            is_active=user.is_active,
        )
