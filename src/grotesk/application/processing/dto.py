from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from grotesk.domain.processing.model import JobId, JobType, ProcessingStatus, TimelineOperation


@dataclass(frozen=True)
class JobHistoryItemDTO:
    status: ProcessingStatus
    message: str


@dataclass(frozen=True)
class ProcessingJobDTO:
    job_id: JobId
    job_type: JobType
    status: ProcessingStatus
    created_at: datetime | None
    source_filename: str | None
    model_name: str | None
    history: list[JobHistoryItemDTO]


@dataclass(frozen=True)
class ProcessingJobDetailDTO:
    job_id: JobId
    job_type: JobType
    status: ProcessingStatus
    created_at: datetime | None
    source_filename: str | None
    model_name: str | None
    prompt_text: str | None
    result_type: str | None
    result_id: UUID | None
    history: list[JobHistoryItemDTO]
    operations: list[TimelineOperation] = field(default_factory=list)
