from dataclasses import dataclass

from grotesk.domain.common.event import Event
from grotesk.domain.identity_access.model import UserId, UserRole


@dataclass(frozen=True)
class UserRegistered(Event):
    user_id: UserId
    role: UserRole
