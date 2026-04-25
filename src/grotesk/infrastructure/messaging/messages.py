import json
from dataclasses import dataclass
from uuid import UUID

from grotesk.domain.common.event import Event
from grotesk.domain.processing.events import TranscriptionJobSubmitted, VideoEditingJobSubmitted
from grotesk.domain.processing.model import JobId, JobType


@dataclass(frozen=True)
class JobSubmittedMessage:
    event_name: str
    job_id: UUID
    job_type: str
    submitted_at: str

    @classmethod
    def from_event(cls, event: Event) -> "JobSubmittedMessage | None":
        if isinstance(event, TranscriptionJobSubmitted):
            return cls(
                event_name=type(event).__name__,
                job_id=event.job_id.value,
                job_type=JobType.TRANSCRIPTION.value,
                submitted_at=event.occurred_at.isoformat(),
            )
        if isinstance(event, VideoEditingJobSubmitted):
            return cls(
                event_name=type(event).__name__,
                job_id=event.job_id.value,
                job_type=JobType.VIDEO_EDITING.value,
                submitted_at=event.occurred_at.isoformat(),
            )
        return None

    @classmethod
    def from_body(cls, body: bytes) -> "JobSubmittedMessage":
        data = json.loads(body.decode("utf-8"))
        return cls(
            event_name=data["event_name"],
            job_id=UUID(data["job_id"]),
            job_type=data["job_type"],
            submitted_at=data["submitted_at"],
        )

    @property
    def job_identifier(self) -> JobId:
        return JobId(self.job_id)

    def to_body(self) -> bytes:
        return json.dumps(
            {
                "event_name": self.event_name,
                "job_id": str(self.job_id),
                "job_type": self.job_type,
                "submitted_at": self.submitted_at,
            },
            sort_keys=True,
        ).encode("utf-8")
