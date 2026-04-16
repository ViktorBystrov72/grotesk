from typing import Protocol

from grotesk.domain.processing.model import JobId, ProcessingJob


class ProcessingJobRepository(Protocol):
    async def add(self, job: ProcessingJob) -> None:
        raise NotImplementedError

    async def get_by_id(self, job_id: JobId) -> ProcessingJob | None:
        raise NotImplementedError

    async def save(self, job: ProcessingJob) -> None:
        raise NotImplementedError
