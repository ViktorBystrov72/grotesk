from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from grotesk.domain.common.entity import Entity
from grotesk.domain.common.primitives import EntityId
from grotesk.domain.identity_access.model import UserId


class DecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class AdminActionId(EntityId):
    pass


@dataclass
class ModerationDecision(Entity):
    decision_type: DecisionType
    target_id: EntityId
    reason: str


@dataclass
class AdminAction(Entity):
    id: AdminActionId
    admin_id: UserId
    action_name: str
    decisions: list[ModerationDecision] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
