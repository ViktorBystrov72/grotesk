from dataclasses import dataclass

from grotesk.application.common.query import Query, QueryHandler
from grotesk.application.processing.dto import JobHistoryItemDTO, ProcessingJobDetailDTO, ProcessingJobDTO
from grotesk.domain.catalog.interfaces import ModelCatalogRepository
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.media_ingestion.interfaces import MediaAssetRepository
from grotesk.domain.processing.interfaces import ProcessingJobRepository
from grotesk.domain.processing.model import JobId
from grotesk.presentation.filenames import extract_display_filename


@dataclass(frozen=True)
class GetUserJobHistory(Query[list[ProcessingJobDTO]]):
    user_id: UserId


class GetUserJobHistoryHandler(QueryHandler[GetUserJobHistory, list[ProcessingJobDTO]]):
    def __init__(
        self,
        processing_job_repository: ProcessingJobRepository,
        media_asset_repository: MediaAssetRepository,
        model_catalog_repository: ModelCatalogRepository,
    ) -> None:
        self._processing_job_repository = processing_job_repository
        self._media_asset_repository = media_asset_repository
        self._model_catalog_repository = model_catalog_repository

    async def _get_source_filename(self, job) -> str | None:
        media_asset = await self._media_asset_repository.get_by_id(job.media_asset_id)
        if media_asset is None:
            return None
        return extract_display_filename(media_asset.location.storage_key)

    async def _get_model_name(self, job) -> str | None:
        model_profile = await self._model_catalog_repository.get_by_id(job.model_id)
        if model_profile is None:
            return None
        return model_profile.name

    async def __call__(self, query: GetUserJobHistory) -> list[ProcessingJobDTO]:
        jobs = await self._processing_job_repository.list_by_user_id(query.user_id)
        filenames = {job.id: await self._get_source_filename(job) for job in jobs}
        model_names = {job.id: await self._get_model_name(job) for job in jobs}
        return [
            ProcessingJobDTO(
                job_id=job.id,
                job_type=job.job_type,
                status=job.status,
                created_at=job.created_at,
                source_filename=filenames.get(job.id),
                model_name=model_names.get(job.id),
                history=[JobHistoryItemDTO(status=record.status, message=record.message) for record in job.history],
            )
            for job in jobs
        ]


@dataclass(frozen=True)
class GetUserJobDetails(Query[ProcessingJobDetailDTO]):
    user_id: UserId
    job_id: JobId


class GetUserJobDetailsHandler(QueryHandler[GetUserJobDetails, ProcessingJobDetailDTO]):
    def __init__(
        self,
        processing_job_repository: ProcessingJobRepository,
        media_asset_repository: MediaAssetRepository,
        model_catalog_repository: ModelCatalogRepository,
    ) -> None:
        self._processing_job_repository = processing_job_repository
        self._media_asset_repository = media_asset_repository
        self._model_catalog_repository = model_catalog_repository

    async def __call__(self, query: GetUserJobDetails) -> ProcessingJobDetailDTO:
        job = await self._processing_job_repository.get_by_id(query.job_id)
        if job is None or job.user_id != query.user_id:
            raise ValueError("Processing job does not exist.")

        media_asset = await self._media_asset_repository.get_by_id(job.media_asset_id)
        model_profile = await self._model_catalog_repository.get_by_id(job.model_id)
        return ProcessingJobDetailDTO(
            job_id=job.id,
            job_type=job.job_type,
            status=job.status,
            created_at=job.created_at,
            source_filename=(
                extract_display_filename(media_asset.location.storage_key) if media_asset is not None else None
            ),
            model_name=model_profile.name if model_profile is not None else None,
            prompt_text=job.prompt_text,
            result_type=job.result_ref.result_type if job.result_ref else None,
            result_id=job.result_ref.result_id.value if job.result_ref else None,
            history=[JobHistoryItemDTO(status=record.status, message=record.message) for record in job.history],
            operations=job.operations,
        )
