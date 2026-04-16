from dataclasses import dataclass

from grotesk.domain.common.event import Event
from grotesk.domain.processing.model import JobId


@dataclass(frozen=True)
class TranscriptionJobSubmitted(Event):
    job_id: JobId


@dataclass(frozen=True)
class VideoEditingJobSubmitted(Event):
    job_id: JobId


@dataclass(frozen=True)
class JobCompleted(Event):
    job_id: JobId


@dataclass(frozen=True)
class JobFailed(Event):
    job_id: JobId
    reason: str
