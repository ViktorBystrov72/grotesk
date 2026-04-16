from sqlalchemy import select
from sqlalchemy.orm import selectinload

from grotesk.domain.processing.interfaces import ProcessingJobRepository
from grotesk.domain.processing.model import JobId, ProcessingJob
from grotesk.infrastructure.db.mappers import processing_job_to_domain
from grotesk.infrastructure.db.models.entities import JobHistoryRecordModel, ProcessingJobModel
from grotesk.infrastructure.db.repositories.base import SQLAlchemyRepository


class ProcessingJobRepositoryImpl(SQLAlchemyRepository, ProcessingJobRepository):
    async def add(self, job: ProcessingJob) -> None:
        model = ProcessingJobModel(
            id=job.id.value,
            user_id=job.user_id.value,
            media_asset_id=job.media_asset_id.value,
            model_id=job.model_id.value,
            job_type=job.job_type,
            estimated_cost_amount=job.estimated_cost.amount,
            estimated_cost_currency=job.estimated_cost.currency,
            status=job.status,
            result_type=job.result_ref.result_type if job.result_ref else None,
            result_id=job.result_ref.result_id.value if job.result_ref else None,
        )
        model.history = [
            JobHistoryRecordModel(
                status=record.status,
                changed_at=record.changed_at,
                message=record.message,
            )
            for record in job.history
        ]
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, job_id: JobId) -> ProcessingJob | None:
        model = await self._session.scalar(
            select(ProcessingJobModel)
            .options(selectinload(ProcessingJobModel.history))
            .where(ProcessingJobModel.id == job_id.value),
        )
        if model is None:
            return None
        return processing_job_to_domain(model)

    async def save(self, job: ProcessingJob) -> None:
        model = await self._session.scalar(
            select(ProcessingJobModel)
            .options(selectinload(ProcessingJobModel.history))
            .where(ProcessingJobModel.id == job.id.value),
        )
        if model is None:
            await self.add(job)
            return

        model.user_id = job.user_id.value
        model.media_asset_id = job.media_asset_id.value
        model.model_id = job.model_id.value
        model.job_type = job.job_type
        model.estimated_cost_amount = job.estimated_cost.amount
        model.estimated_cost_currency = job.estimated_cost.currency
        model.status = job.status
        model.result_type = job.result_ref.result_type if job.result_ref else None
        model.result_id = job.result_ref.result_id.value if job.result_ref else None
        model.history = [
            JobHistoryRecordModel(
                status=record.status,
                changed_at=record.changed_at,
                message=record.message,
            )
            for record in job.history
        ]
        await self._session.flush()
