from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PricingRuleResponse(BaseModel):
    capability: str
    amount: Decimal
    currency: str


class ModelResponse(BaseModel):
    id: UUID
    name: str
    capabilities: list[str]
    pricing_rules: list[PricingRuleResponse]
