from sqlalchemy.ext.asyncio import AsyncSession

from grotesk.application.billing.commands import (
    ApproveTopUpHandler,
    DebitBalanceHandler,
    TopUpBalanceHandler,
)
from grotesk.application.billing.queries import (
    GetUserBalanceHandler,
    GetUserTransactionHistoryHandler,
)
from grotesk.application.identity_access.commands import RegisterUserHandler
from grotesk.application.identity_access.queries import GetUserByEmailHandler, GetUserByIdHandler
from grotesk.application.media_ingestion.commands import UploadMediaAssetHandler
from grotesk.application.processing.commands import (
    SubmitTranscriptionJobHandler,
    SubmitVideoEditingJobHandler,
)
from grotesk.application.processing.queries import GetUserJobHistoryHandler
from grotesk.domain.billing.service import BillingService
from grotesk.domain.media_ingestion.service import MediaIngestionService
from grotesk.infrastructure.db.repositories.billing import (
    AccountBalanceRepositoryImpl,
    BillingTransactionRepositoryImpl,
    TopUpRequestRepositoryImpl,
)
from grotesk.infrastructure.db.repositories.catalog import ModelCatalogRepositoryImpl
from grotesk.infrastructure.db.repositories.media import MediaAssetRepositoryImpl
from grotesk.infrastructure.db.repositories.processing import ProcessingJobRepositoryImpl
from grotesk.infrastructure.db.repositories.user import UserRepositoryImpl
from grotesk.infrastructure.db.uow import SQLAlchemyUnitOfWork
from grotesk.infrastructure.stubs import InMemoryEventPublisher
from grotesk.main.application import Application


def build_application(session: AsyncSession) -> Application:
    user_repository = UserRepositoryImpl(session)
    account_balance_repository = AccountBalanceRepositoryImpl(session)
    top_up_request_repository = TopUpRequestRepositoryImpl(session)
    billing_transaction_repository = BillingTransactionRepositoryImpl(session)
    media_asset_repository = MediaAssetRepositoryImpl(session)
    model_catalog_repository = ModelCatalogRepositoryImpl(session)
    processing_job_repository = ProcessingJobRepositoryImpl(session)

    publisher = InMemoryEventPublisher()
    uow = SQLAlchemyUnitOfWork(session)

    billing_service = BillingService(
        account_balance_repository,
        top_up_request_repository,
        billing_transaction_repository,
    )
    media_ingestion_service = MediaIngestionService(media_asset_repository)

    return Application(
        register_user=RegisterUserHandler(user_repository, billing_service, publisher, uow),
        get_user_by_id=GetUserByIdHandler(user_repository),
        get_user_by_email=GetUserByEmailHandler(user_repository),
        upload_media=UploadMediaAssetHandler(media_ingestion_service, publisher, uow),
        submit_transcription_job=SubmitTranscriptionJobHandler(
            processing_job_repository,
            media_asset_repository,
            model_catalog_repository,
            billing_service,
            publisher,
            uow,
        ),
        submit_video_edit_job=SubmitVideoEditingJobHandler(
            processing_job_repository,
            media_asset_repository,
            model_catalog_repository,
            billing_service,
            publisher,
            uow,
        ),
        approve_top_up=ApproveTopUpHandler(billing_service, publisher, uow),
        top_up_balance=TopUpBalanceHandler(billing_service, publisher, uow),
        debit_balance=DebitBalanceHandler(billing_service, publisher, uow),
        get_user_transaction_history=GetUserTransactionHistoryHandler(billing_transaction_repository),
        get_user_balance=GetUserBalanceHandler(account_balance_repository),
        get_user_job_history=GetUserJobHistoryHandler(processing_job_repository),
    )
