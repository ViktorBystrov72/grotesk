from grotesk.domain.common.service import DomainService
from grotesk.domain.processing.events import JobCompleted, JobFailed
from grotesk.domain.processing.interfaces import ProcessingJobRepository
from grotesk.domain.processing.model import JobId, JobResultRef


class ProcessingService(DomainService):
    def __init__(self, processing_job_repository: ProcessingJobRepository) -> None:
        super().__init__()
        self._processing_job_repository = processing_job_repository

    async def complete_job(
        self,
        job_id: JobId,
        result_ref: JobResultRef,
        completion_message: str = "Job completed",
    ) -> None:
        job = await self._processing_job_repository.get_by_id(job_id)
        if job is None:
            raise ValueError("Processing job does not exist.")

        job.mark_completed(result_ref)
        job.history[-1].message = completion_message
        await self._processing_job_repository.save(job)
        self.record_event(JobCompleted(job_id=job_id))

    async def fail_job(self, job_id: JobId, reason: str) -> None:
        job = await self._processing_job_repository.get_by_id(job_id)
        if job is None:
            raise ValueError("Processing job does not exist.")

        job.mark_failed(reason)
        await self._processing_job_repository.save(job)
        self.record_event(JobFailed(job_id=job_id, reason=reason))
