from dataclasses import dataclass

from grotesk.domain.common.event import Event
from grotesk.domain.media_ingestion.model import MediaAssetId, MediaType


@dataclass(frozen=True)
class MediaAssetUploaded(Event):
    asset_id: MediaAssetId
    media_type: MediaType
