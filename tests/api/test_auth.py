import pytest

from grotesk.presentation.api.routers import auth


@pytest.mark.asyncio
async def test_register_success(client):
    original_hash = auth.get_password_hash
    auth.get_password_hash = lambda p: "hashed_" + p

    try:
        response = await client.post("/auth/register", json={"email": "test@example.com", "password": "password123"})
        assert response.status_code == 200
        assert "user_id" in response.json()
    finally:
        auth.get_password_hash = original_hash


@pytest.mark.asyncio
async def test_register_existing_user(client):
    original_hash = auth.get_password_hash
    auth.get_password_hash = lambda p: "hashed_" + p

    try:
        response = await client.post("/auth/register", json={"email": "exist@example.com", "password": "password123"})
        assert response.status_code == 400
        assert "User already exists" in response.json()["detail"]
    finally:
        auth.get_password_hash = original_hash


@pytest.mark.asyncio
async def test_register_validation_error(client):
    response = await client.post("/auth/register", json={"email": "not-an-email"})  # missing password
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client):
    original_verify = auth.verify_password
    auth.verify_password = lambda p, h: True

    try:
        response = await client.post("/auth/login", json={"email": "test@example.com", "password": "password123"})
        assert response.status_code == 200
        assert "user_id" in response.json()
    finally:
        auth.verify_password = original_verify


@pytest.mark.asyncio
async def test_logout_clears_authenticated_session(client):
    original_verify = auth.verify_password
    auth.verify_password = lambda p, h: True

    try:
        login_response = await client.post("/auth/login", json={"email": "test@example.com", "password": "password123"})
    finally:
        auth.verify_password = original_verify
    assert login_response.status_code == 200

    logout_response = await client.post("/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["status"] == "success"

    me_response = await client.get("/auth/me")
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_credentials(client):
    response = await client.post("/auth/login", json={"email": "test@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_user_not_found(client):
    response = await client.post("/auth/login", json={"email": "wrong@example.com", "password": "password123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"
