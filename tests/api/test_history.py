import pytest


@pytest.mark.asyncio
async def test_get_transactions_success(client):
    response = await client.get("/history/transactions", params={"user_id": "00000000-0000-0000-0000-000000000001"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_transactions_error(client):
    response = await client.get("/history/transactions", params={"user_id": "00000000-0000-0000-0000-000000000400"})
    assert response.status_code == 400
    assert "Error getting transactions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_transactions_invalid_uuid(client):
    response = await client.get("/history/transactions", params={"user_id": "invalid"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_requests_success(client):
    response = await client.get("/history/requests", params={"user_id": "00000000-0000-0000-0000-000000000001"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_requests_error(client):
    response = await client.get("/history/requests", params={"user_id": "00000000-0000-0000-0000-000000000400"})
    assert response.status_code == 400
    assert "Error getting jobs" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_requests_invalid_uuid(client):
    response = await client.get("/history/requests", params={"user_id": "invalid"})
    assert response.status_code == 422
