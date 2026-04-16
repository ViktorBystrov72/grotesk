from dataclasses import dataclass, field
from enum import StrEnum

from grotesk.domain.common.entity import Entity
from grotesk.domain.common.primitives import EntityId, FileLocation
from grotesk.domain.identity_access.model import UserId


class MediaType(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"


class MediaStatus(StrEnum):
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    REJECTED = "rejected"


@dataclass(frozen=True)
class MediaAssetId(EntityId):
    pass


@dataclass
class AttachmentAsset(Entity):
    id: MediaAssetId
    owner_id: UserId
    media_type: MediaType
    location: FileLocation


@dataclass
class MediaAsset(Entity):
    id: MediaAssetId
    owner_id: UserId
    media_type: MediaType
    location: FileLocation
    status: MediaStatus = MediaStatus.UPLOADED
    attachments: list[AttachmentAsset] = field(default_factory=list)

    def mark_validated(self) -> None:
        self.status = MediaStatus.VALIDATED

    def add_attachment(self, attachment: AttachmentAsset) -> None:
        self.attachments.append(attachment)
