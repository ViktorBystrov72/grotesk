from grotesk.application.billing.commands import ApproveTopUpHandler
from grotesk.application.identity_access.commands import RegisterUserHandler
from grotesk.application.media_ingestion.commands import UploadMediaAssetHandler
from grotesk.application.processing.commands import (
    SubmitTranscriptionJobHandler,
    SubmitVideoEditingJobHandler,
)
from grotesk.domain.billing.service import BillingService
from grotesk.domain.media_ingestion.service import MediaIngestionService
from grotesk.infrastructure.stubs import (
    InMemoryAccountBalanceRepository,
    InMemoryEventPublisher,
    InMemoryMediaAssetRepository,
    InMemoryModelCatalogRepository,
    InMemoryProcessingJobRepository,
    InMemoryTopUpRequestRepository,
    InMemoryUnitOfWork,
    InMemoryUserRepository,
)


def build_application() -> dict[str, object]:
    user_repository = InMemoryUserRepository()
    account_balance_repository = InMemoryAccountBalanceRepository()
    top_up_request_repository = InMemoryTopUpRequestRepository()
    media_asset_repository = InMemoryMediaAssetRepository()
    model_catalog_repository = InMemoryModelCatalogRepository()
    processing_job_repository = InMemoryProcessingJobRepository()

    publisher = InMemoryEventPublisher()
    uow = InMemoryUnitOfWork()

    billing_service = BillingService(account_balance_repository, top_up_request_repository)
    media_ingestion_service = MediaIngestionService(media_asset_repository)

    return {
        "register_user": RegisterUserHandler(user_repository, publisher, uow),
        "upload_media": UploadMediaAssetHandler(media_ingestion_service, publisher, uow),
        "submit_transcription_job": SubmitTranscriptionJobHandler(
            processing_job_repository,
            media_asset_repository,
            model_catalog_repository,
            billing_service,
            publisher,
            uow,
        ),
        "submit_video_edit_job": SubmitVideoEditingJobHandler(
            processing_job_repository,
            media_asset_repository,
            model_catalog_repository,
            billing_service,
            publisher,
            uow,
        ),
        "approve_top_up": ApproveTopUpHandler(billing_service, publisher, uow),
    }
