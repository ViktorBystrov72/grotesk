from dataclasses import dataclass

from grotesk.domain.processing.model import JobId, JobType, ProcessingStatus


@dataclass(frozen=True)
class JobHistoryItemDTO:
    status: ProcessingStatus
    message: str


@dataclass(frozen=True)
class ProcessingJobDTO:
    job_id: JobId
    job_type: JobType
    status: ProcessingStatus
    history: list[JobHistoryItemDTO]
