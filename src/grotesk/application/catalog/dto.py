from dataclasses import dataclass

from grotesk.domain.catalog.model import Capability, ModelId


@dataclass(frozen=True)
class PricingRuleDTO:
    capability: Capability
    amount: str
    currency: str


@dataclass(frozen=True)
class ModelProfileDTO:
    model_id: ModelId
    name: str
    capabilities: list[Capability]
    pricing_rules: list[PricingRuleDTO]
