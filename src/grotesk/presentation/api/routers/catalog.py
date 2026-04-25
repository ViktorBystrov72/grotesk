from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends

from grotesk.application.catalog.queries import GetAvailableModels
from grotesk.main.application import Application
from grotesk.presentation.api.dependencies import get_application
from grotesk.presentation.api.schemas.catalog import ModelResponse, PricingRuleResponse

router = APIRouter()


@router.get("/models", response_model=list[ModelResponse])
async def list_models(
    application: Annotated[Application, Depends(get_application)],
) -> list[ModelResponse]:
    models = await application.get_available_models(GetAvailableModels())
    return [
        ModelResponse(
            id=model.model_id.value,
            name=model.name,
            capabilities=[capability.value for capability in model.capabilities],
            pricing_rules=[
                PricingRuleResponse(
                    capability=pricing_rule.capability.value,
                    amount=Decimal(pricing_rule.amount),
                    currency=pricing_rule.currency,
                )
                for pricing_rule in model.pricing_rules
            ],
        )
        for model in models
    ]
