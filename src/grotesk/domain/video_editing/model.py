from dataclasses import dataclass, field

from grotesk.domain.common.entity import Entity
from grotesk.domain.common.primitives import EntityId, TimestampRange
from grotesk.domain.common.value_object import ValueObject
from grotesk.domain.media_ingestion.model import MediaAssetId
from grotesk.domain.processing.model import JobId


@dataclass(frozen=True)
class PromptRequestId(EntityId):
    pass


@dataclass(frozen=True)
class VideoEditResultId(EntityId):
    pass


@dataclass(frozen=True)
class PromptText(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Prompt text cannot be empty.")


@dataclass
class TimelineEditOperation(Entity):
    time_range: TimestampRange
    prompt: PromptText
    reference_asset_id: MediaAssetId | None = None


@dataclass
class PromptRequest(Entity):
    id: PromptRequestId
    source_job_id: JobId
    prompt_text: PromptText
    operations: list[TimelineEditOperation] = field(default_factory=list)


@dataclass
class VideoEditResult(Entity):
    id: VideoEditResultId
    job_id: JobId
    output_asset_id: MediaAssetId
