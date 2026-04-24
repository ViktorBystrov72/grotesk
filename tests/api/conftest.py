from datetime import UTC, datetime
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from grotesk.application.catalog.dto import ModelProfileDTO, PricingRuleDTO
from grotesk.application.identity_access.dto import UserDTO
from grotesk.application.processing.dto import JobHistoryItemDTO, ProcessingJobDetailDTO, ProcessingJobDTO
from grotesk.domain.catalog.model import Capability, ModelId
from grotesk.domain.identity_access.model import UserId, UserRole
from grotesk.domain.processing.model import JobId, JobType, ProcessingStatus
from grotesk.presentation.api.dependencies import get_application
from grotesk.presentation.api.main import create_app

TEST_USER_ID = UserId(UUID("00000000-0000-0000-0000-000000000111"))
TEST_JOB_ID = JobId(UUID("00000000-0000-0000-0000-000000000222"))
TEST_MODEL_ID = ModelId(UUID("00000000-0000-0000-0000-000000000333"))
TEST_PASSWORD_HASH = "test-password-hash"


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
                )
            ]

        if type_name == "GetUserTransactionHistory":
            if str(command_or_query.user_id.value) == "00000000-0000-0000-0000-000000000400":
                raise ValueError("Error getting transactions")
            return []

        if type_name == "GetUserJobHistory":
            if str(command_or_query.user_id.value) == "00000000-0000-0000-0000-000000000400":
                raise ValueError("Error getting jobs")
            return [
                ProcessingJobDTO(
                    job_id=TEST_JOB_ID,
                    job_type=JobType.TRANSCRIPTION,
                    status=ProcessingStatus.COMPLETED,
                    created_at=datetime.now(UTC),
                    history=[
                        JobHistoryItemDTO(
                            status=ProcessingStatus.COMPLETED,
                            message="done",
                        )
                    ],
                )
            ]

        if type_name == "GetUserJobDetails":
            if command_or_query.job_id != TEST_JOB_ID:
                raise ValueError("Processing job does not exist.")
            return ProcessingJobDetailDTO(
                job_id=TEST_JOB_ID,
                job_type=JobType.TRANSCRIPTION,
                status=ProcessingStatus.COMPLETED,
                created_at=datetime.now(UTC),
                prompt_text=None,
                result_type="transcription",
                result_id=None,
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
