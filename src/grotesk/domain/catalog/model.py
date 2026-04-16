from dataclasses import dataclass, field
from enum import StrEnum

from grotesk.domain.common.entity import Entity
from grotesk.domain.common.primitives import EntityId, Money


class Capability(StrEnum):
    TRANSCRIPTION = "transcription"
    DIARIZATION = "diarization"
    VIDEO_EDITING = "video_editing"
    IMAGE_REPLACEMENT = "image_replacement"
    BODY_RESHAPING = "body_reshaping"


@dataclass(frozen=True)
class ModelId(EntityId):
    pass


@dataclass
class PricingRule(Entity):
    capability: Capability
    price: Money


@dataclass
class ModelProfile(Entity):
    id: ModelId
    name: str
    capabilities: list[Capability] = field(default_factory=list)
    pricing_rules: list[PricingRule] = field(default_factory=list)
    is_active: bool = True

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities
