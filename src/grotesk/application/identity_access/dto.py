from dataclasses import dataclass

from grotesk.domain.identity_access.model import UserId, UserRole


@dataclass(frozen=True)
class UserDTO:
    user_id: UserId
    email: str
    password_hash: str
    role: UserRole
    is_active: bool
