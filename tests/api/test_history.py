import pytest


@pytest.mark.asyncio
async def test_get_transactions_success(client):
    response = await client.get("/history/transactions", params={"user_id": "00000000-0000-0000-0000-000000000111"})
    assert response.status_code == 200
    transactions = response.json()
    assert transactions == [
        {
            "id": "top-up",
            "amount": "100.00",
            "type": "top_up",
            "created_at": transactions[0]["created_at"],
        },
        {
            "id": "00000000-0000-0000-0000-000000000222",
            "amount": "10.00",
            "type": "charge",
            "created_at": transactions[1]["created_at"],
        },
    ]


@pytest.mark.asyncio
async def test_get_transactions_without_user_context_returns_unauthorized(client):
    response = await client.get("/history/transactions")
    assert response.status_code == 401


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
    response = await client.get("/history/requests", params={"user_id": "00000000-0000-0000-0000-000000000111"})
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "00000000-0000-0000-0000-000000000222",
            "type": "transcription",
            "status": "completed",
            "created_at": response.json()[0]["created_at"],
        }
    ]


@pytest.mark.asyncio
async def test_get_requests_without_user_context_returns_unauthorized(client):
    response = await client.get("/history/requests")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_requests_error(client):
    response = await client.get("/history/requests", params={"user_id": "00000000-0000-0000-0000-000000000400"})
    assert response.status_code == 400
    assert "Error getting jobs" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_requests_invalid_uuid(client):
    response = await client.get("/history/requests", params={"user_id": "invalid"})
    assert response.status_code == 422
