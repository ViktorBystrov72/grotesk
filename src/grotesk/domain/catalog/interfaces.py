from typing import Protocol

from grotesk.domain.catalog.model import ModelId, ModelProfile


class ModelCatalogRepository(Protocol):
    async def get_by_id(self, model_id: ModelId) -> ModelProfile | None:
        raise NotImplementedError

    async def list_active(self) -> list[ModelProfile]:
        raise NotImplementedError

    async def save(self, profile: ModelProfile) -> None:
        raise NotImplementedError
