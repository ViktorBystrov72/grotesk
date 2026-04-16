from grotesk.domain.common.service import DomainService
from grotesk.domain.media_ingestion.events import MediaAssetUploaded
from grotesk.domain.media_ingestion.interfaces import MediaAssetRepository
from grotesk.domain.media_ingestion.model import MediaAsset


class MediaIngestionService(DomainService):
    def __init__(self, media_asset_repository: MediaAssetRepository) -> None:
        super().__init__()
        self._media_asset_repository = media_asset_repository

    async def register_asset(self, asset: MediaAsset) -> None:
        await self._media_asset_repository.add(asset)
        self.record_event(MediaAssetUploaded(asset_id=asset.id, media_type=asset.media_type))
