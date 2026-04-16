from dataclasses import dataclass

from grotesk.application.common.query import Query, QueryHandler
from grotesk.application.processing.dto import JobHistoryItemDTO, ProcessingJobDTO
from grotesk.domain.processing.interfaces import ProcessingJobRepository
from grotesk.domain.processing.model import JobId


@dataclass(frozen=True)
class GetJobHistory(Query[ProcessingJobDTO]):
    job_id: JobId


class GetJobHistoryHandler(QueryHandler[GetJobHistory, ProcessingJobDTO]):
    def __init__(self, processing_job_repository: ProcessingJobRepository) -> None:
        self._processing_job_repository = processing_job_repository

    async def __call__(self, query: GetJobHistory) -> ProcessingJobDTO:
        job = await self._processing_job_repository.get_by_id(query.job_id)
        if job is None:
            raise ValueError("Processing job does not exist.")

        return ProcessingJobDTO(
            job_id=job.id,
            job_type=job.job_type,
            status=job.status,
            history=[
                JobHistoryItemDTO(status=record.status, message=record.message)
                for record in job.history
            ],
        )
