from dataclasses import dataclass
from enum import StrEnum

from grotesk.domain.common.entity import Entity
from grotesk.domain.common.primitives import EntityId
from grotesk.domain.common.value_object import ValueObject


class UserRole(StrEnum):
    CUSTOMER = "customer"
    ADMIN = "admin"


@dataclass(frozen=True)
class UserId(EntityId):
    pass


@dataclass(frozen=True)
class Email(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if "@" not in self.value:
            raise ValueError("Email must contain '@'.")


@dataclass(frozen=True)
class PasswordHash(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("Password hash cannot be empty.")


@dataclass
class Credential(Entity):
    email: Email
    password_hash: PasswordHash


@dataclass
class User(Entity):
    id: UserId
    credential: Credential
    role: UserRole
    is_active: bool = True

    def deactivate(self) -> None:
        self.is_active = False
