from dataclasses import dataclass

from grotesk.application.common.command import Command, CommandHandler
from grotesk.application.common.interfaces import EventPublisher, UnitOfWork
from grotesk.domain.identity_access.events import UserRegistered
from grotesk.domain.identity_access.interfaces import UserRepository
from grotesk.domain.identity_access.model import Credential, Email, PasswordHash, User, UserId, UserRole


@dataclass(frozen=True)
class RegisterUser(Command[UserId]):
    user_id: UserId
    email: str
    password_hash: str
    role: UserRole = UserRole.CUSTOMER


class RegisterUserHandler(CommandHandler[RegisterUser, UserId]):
    def __init__(self, user_repository: UserRepository, publisher: EventPublisher, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._publisher = publisher
        self._uow = uow

    async def __call__(self, command: RegisterUser) -> UserId:
        email = Email(command.email)
        existing_user = await self._user_repository.get_by_email(email)
        if existing_user is not None:
            raise ValueError("A user with this email already exists.")

        user = User(
            id=command.user_id,
            credential=Credential(email=email, password_hash=PasswordHash(command.password_hash)),
            role=command.role,
        )
        await self._user_repository.add(user)
        await self._publisher.publish([UserRegistered(user_id=user.id, role=user.role)])
        await self._uow.commit()
        return user.id
