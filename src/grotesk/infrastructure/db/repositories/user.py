from sqlalchemy import select

from grotesk.domain.identity_access.interfaces import UserRepository
from grotesk.domain.identity_access.model import Email, User, UserId
from grotesk.infrastructure.db.mappers import user_to_domain
from grotesk.infrastructure.db.models.entities import UserModel
from grotesk.infrastructure.db.repositories.base import SQLAlchemyRepository


class UserRepositoryImpl(SQLAlchemyRepository, UserRepository):
    async def add(self, user: User) -> None:
        self._session.add(
            UserModel(
                id=user.id.value,
                email=user.credential.email.value,
                password_hash=user.credential.password_hash.value,
                role=user.role,
                is_active=user.is_active,
            ),
        )
        await self._session.flush()

    async def get_by_id(self, user_id: UserId) -> User | None:
        model = await self._session.get(UserModel, user_id.value)
        if model is None:
            return None
        return user_to_domain(model)

    async def get_by_email(self, email: Email) -> User | None:
        model = await self._session.scalar(select(UserModel).where(UserModel.email == email.value))
        if model is None:
            return None
        return user_to_domain(model)
