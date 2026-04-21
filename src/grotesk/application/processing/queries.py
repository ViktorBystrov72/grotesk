from dataclasses import dataclass

from grotesk.application.common.query import Query, QueryHandler
from grotesk.application.processing.dto import JobHistoryItemDTO, ProcessingJobDTO
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.processing.interfaces import ProcessingJobRepository


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
