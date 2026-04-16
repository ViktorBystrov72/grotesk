from typing import Protocol

from grotesk.domain.media_ingestion.model import MediaAsset, MediaAssetId


class MediaAssetRepository(Protocol):
    async def add(self, asset: MediaAsset) -> None:
        raise NotImplementedError

    async def get_by_id(self, asset_id: MediaAssetId) -> MediaAsset | None:
        raise NotImplementedError

    async def save(self, asset: MediaAsset) -> None:
        raise NotImplementedError
