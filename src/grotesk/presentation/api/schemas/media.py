from uuid import UUID

from pydantic import BaseModel

from grotesk.domain.media_ingestion.model import MediaStatus, MediaType


class MediaUploadResponse(BaseModel):
    media_asset_id: UUID
    media_type: MediaType
    status: MediaStatus
    storage_key: str
