import io

import pytest

from grotesk.presentation.api.routers import auth


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
async def test_home_page_renders(client) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "Grotesk".encode() in response.content


@pytest.mark.asyncio
async def test_cabinet_page_requires_login_redirect(client) -> None:
    response = await client.get("/cabinet", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_cabinet_page_renders_for_logged_user(client) -> None:
    await login(client)

    response = await client.get("/cabinet")

    assert response.status_code == 200
    assert "Личный кабинет".encode() in response.content


@pytest.mark.asyncio
async def test_transcription_form_submits_job(client) -> None:
    await login(client)

    response = await client.post(
        "/cabinet/transcription",
        data={"model_id": "00000000-0000-0000-0000-000000000333"},
        files={"file": ("sample.wav", io.BytesIO(b"audio-bytes"), "audio/wav")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/cabinet/jobs/")


@pytest.mark.asyncio
async def test_history_page_renders(client) -> None:
    await login(client)

    response = await client.get("/cabinet/history")

    assert response.status_code == 200
    assert "История задач".encode() in response.content
