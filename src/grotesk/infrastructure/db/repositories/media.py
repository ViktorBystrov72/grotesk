from sqlalchemy import select
from sqlalchemy.orm import selectinload

from grotesk.domain.media_ingestion.interfaces import MediaAssetRepository
from grotesk.domain.media_ingestion.model import MediaAsset, MediaAssetId
from grotesk.infrastructure.db.mappers import media_asset_to_domain
from grotesk.infrastructure.db.models.entities import AttachmentAssetModel, MediaAssetModel
from grotesk.infrastructure.db.repositories.base import SQLAlchemyRepository


class MediaAssetRepositoryImpl(SQLAlchemyRepository, MediaAssetRepository):
    async def add(self, asset: MediaAsset) -> None:
        model = MediaAssetModel(
            id=asset.id.value,
            owner_id=asset.owner_id.value,
            media_type=asset.media_type,
            location=asset.location.storage_key,
            status=asset.status,
        )
        model.attachments = [
            AttachmentAssetModel(
                id=attachment.id.value,
                owner_id=attachment.owner_id.value,
                media_type=attachment.media_type,
                location=attachment.location.storage_key,
            )
            for attachment in asset.attachments
        ]
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, asset_id: MediaAssetId) -> MediaAsset | None:
        model = await self._session.scalar(
            select(MediaAssetModel)
            .options(selectinload(MediaAssetModel.attachments))
            .where(MediaAssetModel.id == asset_id.value),
        )
        if model is None:
            return None
        return media_asset_to_domain(model)

    async def save(self, asset: MediaAsset) -> None:
        model = await self._session.scalar(
            select(MediaAssetModel)
            .options(selectinload(MediaAssetModel.attachments))
            .where(MediaAssetModel.id == asset.id.value),
        )
        if model is None:
            await self.add(asset)
            return

        model.owner_id = asset.owner_id.value
        model.media_type = asset.media_type
        model.location = asset.location.storage_key
        model.status = asset.status
        model.attachments = [
            AttachmentAssetModel(
                id=attachment.id.value,
                owner_id=attachment.owner_id.value,
                media_type=attachment.media_type,
                location=attachment.location.storage_key,
            )
            for attachment in asset.attachments
        ]
        await self._session.flush()
