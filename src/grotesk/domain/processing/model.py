from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from grotesk.domain.catalog.model import ModelId
from grotesk.domain.common.entity import Entity
from grotesk.domain.common.primitives import EntityId, Money, TimestampRange
from grotesk.domain.common.value_object import ValueObject
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.media_ingestion.model import MediaAssetId


class JobType(StrEnum):
    TRANSCRIPTION = "transcription"
    VIDEO_EDITING = "video_editing"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class JobId(EntityId):
    pass


@dataclass(frozen=True)
class JobResultRef(ValueObject):
    result_type: str
    result_id: EntityId


@dataclass(frozen=True)
class TimelineOperation(ValueObject):
    start_second: int
    end_second: int
    prompt: str
    reference_asset_id: MediaAssetId | None = None

    def __post_init__(self) -> None:
        TimestampRange(self.start_second, self.end_second)
        if not self.prompt.strip():
            raise ValueError("Timeline operation prompt cannot be empty.")


@dataclass
class JobHistoryRecord(Entity):
    status: ProcessingStatus
    changed_at: datetime | None = None
    message: str = ""


@dataclass
class ProcessingJob(Entity):
    id: JobId
    user_id: UserId
    media_asset_id: MediaAssetId
    model_id: ModelId
    job_type: JobType
    estimated_cost: Money
    status: ProcessingStatus = ProcessingStatus.PENDING
    created_at: datetime | None = None
    result_ref: JobResultRef | None = None
    prompt_text: str | None = None
    operations: list[TimelineOperation] = field(default_factory=list)
    history: list[JobHistoryRecord] = field(default_factory=list)

    def queue(self) -> None:
        self.status = ProcessingStatus.QUEUED
        self.history.append(JobHistoryRecord(status=self.status, message="Job queued"))

    def mark_running(self) -> None:
        self.status = ProcessingStatus.RUNNING
        self.history.append(JobHistoryRecord(status=self.status, message="Job started"))

    def mark_completed(self, result_ref: JobResultRef) -> None:
        self.status = ProcessingStatus.COMPLETED
        self.result_ref = result_ref
        self.history.append(JobHistoryRecord(status=self.status, message="Job completed"))

    def mark_failed(self, message: str) -> None:
        self.status = ProcessingStatus.FAILED
        self.history.append(JobHistoryRecord(status=self.status, message=message))

    def mark_canceled(self, message: str = "Job canceled by user") -> None:
        self.status = ProcessingStatus.CANCELED
        self.history.append(JobHistoryRecord(status=self.status, message=message))
