from dataclasses import dataclass, field

from grotesk.domain.common.entity import Entity
from grotesk.domain.common.primitives import EntityId, TimestampRange
from grotesk.domain.common.value_object import ValueObject
from grotesk.domain.processing.model import JobId


@dataclass(frozen=True)
class TranscriptId(EntityId):
    pass


@dataclass(frozen=True)
class SpeakerLabel(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("Speaker label cannot be empty.")


@dataclass
class SpeakerSegment(Entity):
    speaker: SpeakerLabel
    time_range: TimestampRange
    text: str


@dataclass
class Transcript(Entity):
    id: TranscriptId
    job_id: JobId
    text: str
    segments: list[SpeakerSegment] = field(default_factory=list)
