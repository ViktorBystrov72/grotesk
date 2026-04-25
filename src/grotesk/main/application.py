from dataclasses import dataclass

from grotesk.application.billing.commands import (
    ApproveTopUpHandler,
    DebitBalanceHandler,
    TopUpBalanceHandler,
)
from grotesk.application.billing.queries import (
    GetUserBalanceHandler,
    GetUserTransactionHistoryHandler,
)
from grotesk.application.catalog.queries import GetAvailableModelsHandler
from grotesk.application.identity_access.commands import RegisterUserHandler
from grotesk.application.identity_access.queries import GetUserByEmailHandler, GetUserByIdHandler
from grotesk.application.media_ingestion.commands import UploadMediaAssetHandler
from grotesk.application.processing.commands import (
    CancelProcessingJobHandler,
    SubmitTranscriptionJobHandler,
    SubmitVideoEditingJobHandler,
)
from grotesk.application.processing.queries import GetUserJobDetailsHandler, GetUserJobHistoryHandler


@dataclass(frozen=True)
class Application:
    # Identity & Access
    register_user: RegisterUserHandler
    get_user_by_id: GetUserByIdHandler
    get_user_by_email: GetUserByEmailHandler

    # Media Ingestion
    upload_media: UploadMediaAssetHandler

    # Catalog
    get_available_models: GetAvailableModelsHandler

    # Processing
    submit_transcription_job: SubmitTranscriptionJobHandler
    submit_video_edit_job: SubmitVideoEditingJobHandler
    cancel_processing_job: CancelProcessingJobHandler
    get_user_job_history: GetUserJobHistoryHandler
    get_user_job_detail: GetUserJobDetailsHandler

    # Billing
    approve_top_up: ApproveTopUpHandler
    top_up_balance: TopUpBalanceHandler
    debit_balance: DebitBalanceHandler
    get_user_transaction_history: GetUserTransactionHistoryHandler
    get_user_balance: GetUserBalanceHandler
