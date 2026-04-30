import pytest
from httpx import ASGITransport, AsyncClient

from grotesk.presentation.api.dependencies import get_application
from grotesk.presentation.api.main import create_app


@pytest.mark.asyncio
async def test_get_balance_success(client):
    response = await client.get("/balance", params={"user_id": "00000000-0000-0000-0000-000000000001"})
    assert response.status_code == 200
    assert float(response.json()["balance"]) == 100.0


@pytest.mark.asyncio
async def test_get_balance_without_user_context_returns_unauthorized(client):
    response = await client.get("/balance")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_balance_not_found(client):
    response = await client.get("/balance", params={"user_id": "00000000-0000-0000-0000-000000000404"})
    assert response.status_code == 404
    assert "Balance not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_balance_invalid_uuid(client):
    response = await client.get("/balance", params={"user_id": "invalid-uuid"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_top_up_success(client):
    response = await client.post(
        "/balance/top-up",
        params={"user_id": "00000000-0000-0000-0000-000000000001"},
        json={"amount": 50.0},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "request_id" in response.json()


@pytest.mark.asyncio
async def test_top_up_without_user_context_returns_unauthorized(client):
    response = await client.post("/balance/top-up", json={"amount": 50.0})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_top_up_negative_amount(client):
    response = await client.post(
        "/balance/top-up",
        params={"user_id": "00000000-0000-0000-0000-000000000001"},
        json={"amount": -50.0},
    )
    assert response.status_code == 400
    assert "Money amount must be non-negative" in response.json()["detail"]


@pytest.mark.asyncio
async def test_top_up_invalid_uuid(client):
    response = await client.post(
        "/balance/top-up",
        params={"user_id": "invalid-uuid"},
        json={"amount": 50.0},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_top_up_application_value_error_returns_400():
    app = create_app()

    class _FailingApplication:
        async def top_up_balance(self, _command):
            raise ValueError("top up failed")

    async def _override_get_application():
        return _FailingApplication()

    app.dependency_overrides[get_application] = _override_get_application  # type: ignore

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as local_client:
        response = await local_client.post(
            "/balance/top-up",
            params={"user_id": "00000000-0000-0000-0000-000000000001"},
            json={"amount": 50.0},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "top up failed"
