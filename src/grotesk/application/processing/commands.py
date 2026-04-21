from dataclasses import dataclass

from grotesk.application.common.command import Command, CommandHandler
from grotesk.application.common.interfaces import EventPublisher, UnitOfWork
from grotesk.domain.billing.service import BillingService
from grotesk.domain.catalog.interfaces import ModelCatalogRepository
from grotesk.domain.catalog.model import Capability, ModelId
from grotesk.domain.common.primitives import Money
from grotesk.domain.identity_access.model import UserId
from grotesk.domain.media_ingestion.interfaces import MediaAssetRepository
from grotesk.domain.media_ingestion.model import MediaAssetId, MediaType
from grotesk.domain.processing.events import TranscriptionJobSubmitted, VideoEditingJobSubmitted
from grotesk.domain.processing.interfaces import ProcessingJobRepository
from grotesk.domain.processing.model import JobId, JobType, ProcessingJob


@dataclass(frozen=True)
class SubmitTranscriptionJob(Command[JobId]):
    job_id: JobId
    user_id: UserId
    media_asset_id: MediaAssetId
    model_id: ModelId
    estimated_cost: Money


class SubmitTranscriptionJobHandler(CommandHandler[SubmitTranscriptionJob, JobId]):
    def __init__(
        self,
        processing_job_repository: ProcessingJobRepository,
        media_asset_repository: MediaAssetRepository,
        model_catalog_repository: ModelCatalogRepository,
        billing_service: BillingService,
        publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._processing_job_repository = processing_job_repository
        self._media_asset_repository = media_asset_repository
        self._model_catalog_repository = model_catalog_repository
        self._billing_service = billing_service
        self._publisher = publisher
        self._uow = uow

    async def __call__(self, command: SubmitTranscriptionJob) -> JobId:
        asset = await self._media_asset_repository.get_by_id(command.media_asset_id)
        if asset is None or asset.media_type != MediaType.AUDIO:
            raise ValueError("Transcription requires an audio asset.")

        model = await self._model_catalog_repository.get_by_id(command.model_id)
        if model is None or not model.supports(Capability.TRANSCRIPTION):
            raise ValueError("The selected model does not support transcription.")

        job = ProcessingJob(
            id=command.job_id,
            user_id=command.user_id,
            media_asset_id=command.media_asset_id,
            model_id=command.model_id,
            job_type=JobType.TRANSCRIPTION,
            estimated_cost=command.estimated_cost,
        )
        job.queue()

        await self._processing_job_repository.add(job)
        await self._billing_service.reserve_credits(command.user_id, command.job_id, command.estimated_cost)

        events = [TranscriptionJobSubmitted(job_id=command.job_id), *self._billing_service.pull_events()]
        await self._publisher.publish(events)
        await self._uow.commit()
        return command.job_id


@dataclass(frozen=True)
class SubmitVideoEditingJob(Command[JobId]):
    job_id: JobId
    user_id: UserId
    media_asset_id: MediaAssetId
    model_id: ModelId
    estimated_cost: Money


class SubmitVideoEditingJobHandler(CommandHandler[SubmitVideoEditingJob, JobId]):
    def __init__(
        self,
        processing_job_repository: ProcessingJobRepository,
        media_asset_repository: MediaAssetRepository,
        model_catalog_repository: ModelCatalogRepository,
        billing_service: BillingService,
        publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._processing_job_repository = processing_job_repository
        self._media_asset_repository = media_asset_repository
        self._model_catalog_repository = model_catalog_repository
        self._billing_service = billing_service
        self._publisher = publisher
        self._uow = uow

    async def __call__(self, command: SubmitVideoEditingJob) -> JobId:
        asset = await self._media_asset_repository.get_by_id(command.media_asset_id)
        if asset is None or asset.media_type != MediaType.VIDEO:
            raise ValueError("Video editing requires a video asset.")

        model = await self._model_catalog_repository.get_by_id(command.model_id)
        if model is None or not model.supports(Capability.VIDEO_EDITING):
            raise ValueError("The selected model does not support video editing.")

        job = ProcessingJob(
            id=command.job_id,
            user_id=command.user_id,
            media_asset_id=command.media_asset_id,
            model_id=command.model_id,
            job_type=JobType.VIDEO_EDITING,
            estimated_cost=command.estimated_cost,
        )
        job.queue()

        await self._processing_job_repository.add(job)
        await self._billing_service.reserve_credits(command.user_id, command.job_id, command.estimated_cost)

        events = [VideoEditingJobSubmitted(job_id=command.job_id), *self._billing_service.pull_events()]
        await self._publisher.publish(events)
        await self._uow.commit()
        return command.job_id
