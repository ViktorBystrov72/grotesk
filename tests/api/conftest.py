from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from grotesk.application.identity_access.dto import UserDTO
from grotesk.domain.identity_access.model import UserId, UserRole
from grotesk.presentation.api.dependencies import get_application
from grotesk.presentation.api.main import create_app


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
                user_id=UserId(uuid4()),
                email=command_or_query.email,
                password_hash="$2b$12$vI8aWBnW3fID.ZQ4/zo1G.q1lRps.9cGLcZEiGDMVr5yUP1KUOYTa",  # bcrypt hash
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

        if type_name == "GetUserTransactionHistory":
            if str(command_or_query.user_id.value) == "00000000-0000-0000-0000-000000000400":
                raise ValueError("Error getting transactions")
            return []

        if type_name == "GetUserJobHistory":
            if str(command_or_query.user_id.value) == "00000000-0000-0000-0000-000000000400":
                raise ValueError("Error getting jobs")
            return []

        raise NotImplementedError(f"Mock not implemented for {type_name}")

    async def register_user(self, command):
        return await self(command)

    async def get_user_by_email(self, query):
        return await self(query)

    async def get_user_balance(self, query):
        return await self(query)

    async def top_up_balance(self, command):
        return await self(command)

    async def submit_transcription_job(self, command):
        return await self(command)

    async def submit_video_edit_job(self, command):
        return await self(command)

    async def get_user_transaction_history(self, query):
        return await self(query)

    async def get_user_job_history(self, query):
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
