from dataclasses import dataclass

from grotesk.application.catalog.dto import ModelProfileDTO, PricingRuleDTO
from grotesk.application.common.query import Query, QueryHandler
from grotesk.domain.catalog.interfaces import ModelCatalogRepository


@dataclass(frozen=True)
class GetAvailableModels(Query[list[ModelProfileDTO]]):
    pass


class GetAvailableModelsHandler(QueryHandler[GetAvailableModels, list[ModelProfileDTO]]):
    def __init__(self, model_catalog_repository: ModelCatalogRepository) -> None:
        self._model_catalog_repository = model_catalog_repository

    async def __call__(self, query: GetAvailableModels) -> list[ModelProfileDTO]:
        del query
        models = await self._model_catalog_repository.list_active()
        return [
            ModelProfileDTO(
                model_id=model.id,
                name=model.name,
                capabilities=list(model.capabilities),
                pricing_rules=[
                    PricingRuleDTO(
                        capability=pricing_rule.capability,
                        amount=str(pricing_rule.price.amount),
                        currency=pricing_rule.price.currency,
                    )
                    for pricing_rule in model.pricing_rules
                ],
            )
            for model in models
        ]
