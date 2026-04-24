from dataclasses import dataclass

from grotesk.application.common.query import Query, QueryHandler
from grotesk.application.processing.dto import JobHistoryItemDTO, ProcessingJobDetailDTO, ProcessingJobDTO
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.processing.interfaces import ProcessingJobRepository
from grotesk.domain.processing.model import JobId


@dataclass(frozen=True)
class GetUserJobHistory(Query[list[ProcessingJobDTO]]):
    user_id: UserId


class GetUserJobHistoryHandler(QueryHandler[GetUserJobHistory, list[ProcessingJobDTO]]):
    def __init__(self, processing_job_repository: ProcessingJobRepository) -> None:
        self._processing_job_repository = processing_job_repository

    async def __call__(self, query: GetUserJobHistory) -> list[ProcessingJobDTO]:
        jobs = await self._processing_job_repository.list_by_user_id(query.user_id)
        return [
            ProcessingJobDTO(
                job_id=job.id,
                job_type=job.job_type,
                status=job.status,
                created_at=job.created_at,
                history=[JobHistoryItemDTO(status=record.status, message=record.message) for record in job.history],
            )
            for job in jobs
        ]


@dataclass(frozen=True)
class GetUserJobDetails(Query[ProcessingJobDetailDTO]):
    user_id: UserId
    job_id: JobId


class GetUserJobDetailsHandler(QueryHandler[GetUserJobDetails, ProcessingJobDetailDTO]):
    def __init__(self, processing_job_repository: ProcessingJobRepository) -> None:
        self._processing_job_repository = processing_job_repository

    async def __call__(self, query: GetUserJobDetails) -> ProcessingJobDetailDTO:
        job = await self._processing_job_repository.get_by_id(query.job_id)
        if job is None or job.user_id != query.user_id:
            raise ValueError("Processing job does not exist.")

        return ProcessingJobDetailDTO(
            job_id=job.id,
            job_type=job.job_type,
            status=job.status,
            created_at=job.created_at,
            prompt_text=job.prompt_text,
            result_type=job.result_ref.result_type if job.result_ref else None,
            result_id=job.result_ref.result_id.value if job.result_ref else None,
            history=[JobHistoryItemDTO(status=record.status, message=record.message) for record in job.history],
        )
