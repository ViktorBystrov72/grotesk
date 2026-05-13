from datetime import UTC, datetime
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from grotesk.application.billing.dto import BillingTransactionDTO
from grotesk.application.catalog.dto import ModelProfileDTO, PricingRuleDTO
from grotesk.application.identity_access.dto import UserDTO
from grotesk.application.processing.dto import JobHistoryItemDTO, ProcessingJobDetailDTO, ProcessingJobDTO
from grotesk.domain.billing.model import TransactionType
from grotesk.domain.catalog.model import Capability, ModelId
from grotesk.domain.identity_access.model import UserId, UserRole
from grotesk.domain.processing.model import JobId, JobType, ProcessingStatus
from grotesk.presentation.api.dependencies import get_application
from grotesk.presentation.api.main import create_app
from grotesk.presentation.helpers import get_media_storage_root

TEST_USER_ID = UserId(UUID("00000000-0000-0000-0000-000000000111"))
TEST_JOB_ID = JobId(UUID("00000000-0000-0000-0000-000000000222"))
TEST_ACTIVE_JOB_ID = JobId(UUID("00000000-0000-0000-0000-000000000223"))
TEST_VIDEO_DETAIL_JOB_ID = JobId(UUID("00000000-0000-0000-0000-000000000555"))
TEST_MODEL_ID = ModelId(UUID("00000000-0000-0000-0000-000000000333"))
TEST_VIDEO_EDIT_MODEL_ID = ModelId(UUID("00000000-0000-0000-0000-000000000444"))
TEST_PASSWORD_HASH = "test-password-hash"


def ensure_test_job_source_media_file() -> str:
    media_root = get_media_storage_root()
    audio_dir = media_root / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    path = audio_dir / "test-job-source.wav"
    if not path.exists():
        path.write_bytes(b"fake-wav")
    return str(path.resolve())


TEST_JOB_SOURCE_MEDIA_PATH = ensure_test_job_source_media_file()


def ensure_test_video_job_source_media_file() -> str:
    media_root = get_media_storage_root()
    video_dir = media_root / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    path = video_dir / "test-job-source.mp4"
    if not path.exists():
        path.write_bytes(b"fake-mp4")
    return str(path.resolve())


TEST_VIDEO_JOB_SOURCE_MEDIA_PATH = ensure_test_video_job_source_media_file()


class MockApplication:
    async def __call__(self, command_or_query):
        type_name = type(command_or_query).__name__

        if type_name == "RegisterUser":
            if command_or_query.email == "exist@example.com":
                raise ValueError("User already exists")
            return command_or_query.user_id

        if type_name == "GetUserByEmail":
            if command_or_query.email == "wrong@example.com":
                raise ValueError("User not found")
            return UserDTO(
                user_id=TEST_USER_ID,
                email=command_or_query.email,
                password_hash=TEST_PASSWORD_HASH,
                role=UserRole.CUSTOMER,
                is_active=True,
            )

        if type_name == "GetUserById":
            if command_or_query.user_id != TEST_USER_ID:
                raise ValueError("User does not exist")
            return UserDTO(
                user_id=TEST_USER_ID,
                email="test@example.com",
                password_hash=TEST_PASSWORD_HASH,
                role=UserRole.CUSTOMER,
                is_active=True,
            )

        if type_name == "GetUserBalance":
            if str(command_or_query.user_id.value) == "00000000-0000-0000-0000-000000000404":
                raise ValueError("Balance not found")
            return "100.0"

        if type_name == "TopUpBalance":
            if command_or_query.amount.amount < 0:
                raise ValueError("Amount must be positive")
            return None

        if type_name == "SubmitTranscriptionJob" or type_name == "SubmitVideoEditingJob":
            if str(command_or_query.media_asset_id.value) == "00000000-0000-0000-0000-000000000400":
                raise ValueError("Invalid asset")
            return command_or_query.job_id

        if type_name == "CancelProcessingJob":
            if command_or_query.job_id not in {TEST_JOB_ID, TEST_ACTIVE_JOB_ID}:
                raise ValueError("Processing job does not exist.")
            return command_or_query.job_id

        if type_name == "UploadMediaAsset":
            return command_or_query.asset

        if type_name == "GetAvailableModels":
            return [
                ModelProfileDTO(
                    model_id=TEST_MODEL_ID,
                    name="openai/whisper-large-v3-turbo",
                    capabilities=[Capability.TRANSCRIPTION, Capability.DIARIZATION],
                    pricing_rules=[
                        PricingRuleDTO(
                            capability=Capability.TRANSCRIPTION,
                            amount="3.00",
                            currency="CREDIT",
                        )
                    ],
                ),
                ModelProfileDTO(
                    model_id=TEST_VIDEO_EDIT_MODEL_ID,
                    name="decart-ai/Lucy-Edit-Dev",
                    capabilities=[Capability.VIDEO_EDITING, Capability.IMAGE_REPLACEMENT, Capability.BODY_RESHAPING],
                    pricing_rules=[
                        PricingRuleDTO(
                            capability=Capability.VIDEO_EDITING,
                            amount="10.00",
                            currency="CREDIT",
                        ),
                    ],
                ),
            ]

        if type_name == "GetUserTransactionHistory":
            if str(command_or_query.user_id.value) == "00000000-0000-0000-0000-000000000400":
                raise ValueError("Error getting transactions")
            return [
                BillingTransactionDTO(
                    transaction_type=TransactionType.TOP_UP,
                    amount="100.00",
                    currency="CREDIT",
                    created_at=datetime.now(UTC),
                    related_job_id=None,
                ),
                BillingTransactionDTO(
                    transaction_type=TransactionType.CHARGE,
                    amount="10.00",
                    currency="CREDIT",
                    created_at=datetime.now(UTC),
                    related_job_id=TEST_JOB_ID,
                ),
            ]

        if type_name == "GetUserJobHistory":
            if str(command_or_query.user_id.value) == "00000000-0000-0000-0000-000000000400":
                raise ValueError("Error getting jobs")
            return [
                ProcessingJobDTO(
                    job_id=TEST_JOB_ID,
                    job_type=JobType.TRANSCRIPTION,
                    status=ProcessingStatus.COMPLETED,
                    created_at=datetime.now(UTC),
                    source_filename="sample.wav",
                    model_name="openai/whisper-large-v3-turbo",
                    history=[
                        JobHistoryItemDTO(
                            status=ProcessingStatus.COMPLETED,
                            message="done",
                        )
                    ],
                )
            ]

        if type_name == "GetUserJobDetails":
            if command_or_query.job_id == TEST_VIDEO_DETAIL_JOB_ID:
                return ProcessingJobDetailDTO(
                    job_id=TEST_VIDEO_DETAIL_JOB_ID,
                    job_type=JobType.VIDEO_EDITING,
                    status=ProcessingStatus.COMPLETED,
                    created_at=datetime.now(UTC),
                    source_filename="clip.mp4",
                    model_name="decart-ai/Lucy-Edit-Dev",
                    prompt_text="test prompt",
                    result_type="video_editing",
                    result_id=UUID("00000000-0000-0000-0000-000000000666"),
                    history=[
                        JobHistoryItemDTO(status=ProcessingStatus.COMPLETED, message="done"),
                    ],
                    operations=[],
                    source_storage_key=TEST_VIDEO_JOB_SOURCE_MEDIA_PATH,
                )
            if command_or_query.job_id == TEST_ACTIVE_JOB_ID:
                return ProcessingJobDetailDTO(
                    job_id=TEST_ACTIVE_JOB_ID,
                    job_type=JobType.TRANSCRIPTION,
                    status=ProcessingStatus.RUNNING,
                    created_at=datetime.now(UTC),
                    source_filename="active.wav",
                    model_name="openai/whisper-large-v3-turbo",
                    prompt_text=None,
                    result_type=None,
                    result_id=None,
                    source_storage_key=TEST_JOB_SOURCE_MEDIA_PATH,
                    history=[
                        JobHistoryItemDTO(
                            status=ProcessingStatus.QUEUED,
                            message="queued",
                        ),
                        JobHistoryItemDTO(
                            status=ProcessingStatus.RUNNING,
                            message="running",
                        ),
                    ],
                )
            if command_or_query.job_id != TEST_JOB_ID:
                raise ValueError("Processing job does not exist.")
            return ProcessingJobDetailDTO(
                job_id=TEST_JOB_ID,
                job_type=JobType.TRANSCRIPTION,
                status=ProcessingStatus.COMPLETED,
                created_at=datetime.now(UTC),
                source_filename="sample.wav",
                model_name="openai/whisper-large-v3-turbo",
                prompt_text=None,
                result_type="transcription",
                result_id=None,
                source_storage_key=TEST_JOB_SOURCE_MEDIA_PATH,
                history=[
                    JobHistoryItemDTO(
                        status=ProcessingStatus.QUEUED,
                        message="queued",
                    ),
                    JobHistoryItemDTO(
                        status=ProcessingStatus.COMPLETED,
                        message="completed",
                    ),
                ],
            )

        raise NotImplementedError(f"Mock not implemented for {type_name}")

    async def register_user(self, command):
        return await self(command)

    async def get_user_by_email(self, query):
        return await self(query)

    async def get_user_balance(self, query):
        return await self(query)

    async def get_user_by_id(self, query):
        return await self(query)

    async def top_up_balance(self, command):
        return await self(command)

    async def upload_media(self, command):
        return await self(command)

    async def get_available_models(self, query):
        return await self(query)

    async def submit_transcription_job(self, command):
        return await self(command)

    async def submit_video_edit_job(self, command):
        return await self(command)

    async def get_user_transaction_history(self, query):
        return await self(query)

    async def get_user_job_history(self, query):
        return await self(query)

    async def get_user_job_detail(self, query):
        return await self(query)

    async def cancel_processing_job(self, command):
        return await self(command)


@pytest.fixture
def mock_app():
    app = create_app()
    mock_application = MockApplication()

    async def override_get_application():
        return mock_application

    app.dependency_overrides[get_application] = override_get_application  # type: ignore
    return app


@pytest_asyncio.fixture
async def client(mock_app):
    async with AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://test") as ac:
        yield ac
