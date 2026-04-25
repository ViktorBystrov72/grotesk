import io

import pytest

from grotesk.presentation.api.routers import auth


@pytest.mark.asyncio
async def test_healthcheck_success(client) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def login(client) -> None:
    original_verify = auth.verify_password
    auth.verify_password = lambda p, h: True
    try:
        response = await client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
    finally:
        auth.verify_password = original_verify
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_me_success(client) -> None:
    await login(client)

    response = await client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_upload_media_success(client) -> None:
    await login(client)

    response = await client.post(
        "/media/upload",
        files={"file": ("sample.wav", io.BytesIO(b"audio-bytes"), "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["media_type"] == "audio"


@pytest.mark.asyncio
async def test_list_models_success(client) -> None:
    response = await client.get("/catalog/models")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "openai/whisper-large-v3-turbo"


@pytest.mark.asyncio
async def test_job_detail_success(client) -> None:
    await login(client)

    response = await client.get("/jobs/00000000-0000-0000-0000-000000000222")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_job_detail_requires_login(client) -> None:
    response = await client.get("/jobs/00000000-0000-0000-0000-000000000222")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cancel_job_success(client) -> None:
    await login(client)

    response = await client.post("/jobs/00000000-0000-0000-0000-000000000223/cancel")

    assert response.status_code == 200
    assert response.json() == {"status": "canceled"}
