from sqlalchemy import select
from sqlalchemy.orm import selectinload

from grotesk.domain.catalog.interfaces import ModelCatalogRepository
from grotesk.domain.catalog.model import ModelId, ModelProfile
from grotesk.infrastructure.db.mappers import model_profile_to_domain
from grotesk.infrastructure.db.models.entities import (
    ModelCapabilityModel,
    ModelProfileModel,
    PricingRuleModel,
)
from grotesk.infrastructure.db.repositories.base import SQLAlchemyRepository


class ModelCatalogRepositoryImpl(SQLAlchemyRepository, ModelCatalogRepository):
    async def get_by_id(self, model_id: ModelId) -> ModelProfile | None:
        model = await self._session.scalar(
            select(ModelProfileModel)
            .options(
                selectinload(ModelProfileModel.capabilities),
                selectinload(ModelProfileModel.pricing_rules),
            )
            .where(ModelProfileModel.id == model_id.value),
        )
        if model is None:
            return None
        return model_profile_to_domain(model)

    async def save(self, profile: ModelProfile) -> None:
        model = await self._session.scalar(
            select(ModelProfileModel)
            .options(
                selectinload(ModelProfileModel.capabilities),
                selectinload(ModelProfileModel.pricing_rules),
            )
            .where(ModelProfileModel.id == profile.id.value),
        )
        if model is None:
            model = ModelProfileModel(id=profile.id.value)
            self._session.add(model)

        model.name = profile.name
        model.is_active = profile.is_active
        model.capabilities = [ModelCapabilityModel(capability=capability) for capability in profile.capabilities]
        model.pricing_rules = [
            PricingRuleModel(
                capability=pricing_rule.capability,
                amount=pricing_rule.price.amount,
                currency=pricing_rule.price.currency,
            )
            for pricing_rule in profile.pricing_rules
        ]
        await self._session.flush()
