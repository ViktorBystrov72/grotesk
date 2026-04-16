import pytest
from httpx import AsyncClient, ASGITransport

from uuid import uuid4

from grotesk.application.identity_access.dto import UserDTO
from grotesk.domain.identity_access.model import UserId, UserRole
from grotesk.presentation.api.main import create_app
from grotesk.presentation.api.dependencies import get_application


class MockApplication:
    def __init__(self):
        self.registered_users = {}
        self.top_ups = []
        self.jobs = []

    async def __call__(self, command_or_query):
        type_name = type(command_or_query).__name__
        
        if type_name == "RegisterUser":
            self.registered_users[str(command_or_query.user_id.value)] = command_or_query
            return command_or_query.user_id
            
        if type_name == "GetUserByEmail":
            return UserDTO(
                user_id=UserId(uuid4()),
                email=command_or_query.email,
                password_hash="$2b$12$vI8aWBnW3fID.ZQ4/zo1G.q1lRps.9cGLcZEiGDMVr5yUP1KUOYTa", # bcrypt hash for "password123"
                role=UserRole.CUSTOMER,
                is_active=True
            )
            
        if type_name == "GetUserBalance":
            return "100.0"
            
        if type_name == "TopUpBalance":
            self.top_ups.append(command_or_query)
            return None
            
        if type_name == "SubmitTranscriptionJob" or type_name == "SubmitVideoEditingJob":
            self.jobs.append(command_or_query)
            return command_or_query.job_id
            
        if type_name == "GetUserTransactionHistory":
            return []
            
        if type_name == "GetJobHistory":
            return []
            
        raise NotImplementedError(f"Mock not implemented for {type_name}")

    def __getitem__(self, item):
        return self


@pytest.fixture
def mock_app():
    app = create_app()
    mock_application = MockApplication()
    
    async def override_get_application():
        return mock_application
        
    app.dependency_overrides[get_application] = override_get_application
    return app


@pytest.mark.asyncio
async def test_register_endpoint(mock_app):
    async with AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://test") as client:
        response = await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"}
        )
        assert response.status_code == 200
        assert "user_id" in response.json()


@pytest.mark.asyncio
async def test_login_endpoint(mock_app):
    async with AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://test") as client:
        response = await client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password123"}
        )
        assert response.status_code == 200
        assert "user_id" in response.json()


@pytest.mark.asyncio
async def test_get_balance_endpoint(mock_app):
    async with AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://test") as client:
        response = await client.get(
            "/balance",
            params={"user_id": "test-user-id"}
        )
        assert response.status_code == 200
        assert response.json()["balance"] == 100.0


@pytest.mark.asyncio
async def test_top_up_endpoint(mock_app):
    async with AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://test") as client:
        response = await client.post(
            "/balance/top-up",
            params={"user_id": "test-user-id"},
            json={"amount": 50.0}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert "request_id" in response.json()


@pytest.mark.asyncio
async def test_submit_transcription_endpoint(mock_app):
    async with AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://test") as client:
        response = await client.post(
            "/predict/transcription",
            params={"user_id": "test-user-id"},
            json={"media_asset_id": "asset-1", "model_id": "model-1"}
        )
        assert response.status_code == 200
        assert "job_id" in response.json()


@pytest.mark.asyncio
async def test_submit_video_editing_endpoint(mock_app):
    async with AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://test") as client:
        response = await client.post(
            "/predict/video-editing",
            params={"user_id": "test-user-id"},
            json={
                "media_asset_id": "asset-1",
                "model_id": "model-1",
                "prompt_text": "Make it cooler"
            }
        )
        assert response.status_code == 200
        assert "job_id" in response.json()
