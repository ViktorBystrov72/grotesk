import io

import pytest

from grotesk.presentation.api.routers import auth
from grotesk.presentation.web import routes
from tests.api.conftest import TEST_ACTIVE_JOB_ID


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
    assert "Время".encode() in response.content
    assert "Файл".encode() in response.content
    assert "Модель".encode() in response.content
    assert "sample.wav".encode() in response.content
    assert "openai/whisper-large-v3-turbo".encode() in response.content
    assert "Готово".encode() in response.content
    assert b"status-pill--completed" in response.content


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
async def test_transcription_page_lists_supported_formats(client) -> None:
    await login(client)

    response = await client.get("/cabinet/transcription")

    assert response.status_code == 200
    assert "MP3, AAC, OGG, WAV, M4A, FLAC".encode() in response.content
    assert "WAV 16 kHz mono".encode() in response.content


@pytest.mark.asyncio
async def test_video_editing_page_explains_timecode_formats(client) -> None:
    await login(client)

    response = await client.get("/cabinet/video-editing")

    assert response.status_code == 200
    assert "Формат операций:".encode() in response.content
    assert "01:15".encode() in response.content
    assert "Общий prompt".encode() in response.content


@pytest.mark.asyncio
async def test_history_page_renders(client) -> None:
    await login(client)

    response = await client.get("/cabinet/history")

    assert response.status_code == 200
    assert "История задач".encode() in response.content
    assert "Пополнение".encode() in response.content
    assert "Списание".encode() in response.content
    assert b"status-pill--completed" in response.content


@pytest.mark.asyncio
async def test_balance_page_renders_russian_transaction_types(client) -> None:
    await login(client)

    response = await client.get("/cabinet/balance")

    assert response.status_code == 200
    assert "Пополнение".encode() in response.content
    assert "Списание".encode() in response.content


@pytest.mark.asyncio
async def test_job_detail_page_shows_filename_and_time(client) -> None:
    await login(client)

    response = await client.get("/cabinet/jobs/00000000-0000-0000-0000-000000000222")

    assert response.status_code == 200
    assert "Файл:".encode() in response.content
    assert "Время:".encode() in response.content
    assert "sample.wav".encode() in response.content
    assert "Модель:".encode() in response.content
    assert "openai/whisper-large-v3-turbo".encode() in response.content
    assert "Готово".encode() in response.content
    assert "Принято".encode() in response.content
    assert "Отменена".encode() in response.content


@pytest.mark.asyncio
async def test_job_detail_page_renders_book_transcript(client, monkeypatch) -> None:
    await login(client)

    monkeypatch.setattr(routes, "resolve_result_artifact_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        routes,
        "load_json_artifact",
        lambda _artifact_path: {
            "duration_seconds": 12.5,
            "model_name": "openai/whisper-large-v3-turbo",
            "text": "Спикер 1: Привет\n\nСпикер 2: Здравствуйте\n\nСпикер 1: Продолжаем разговор",
            "turns": [
                {"speaker": "Спикер 1", "text": "Привет"},
                {"speaker": "Спикер 2", "text": "Здравствуйте"},
                {"speaker": "Спикер 1", "text": "Продолжаем разговор"},
            ],
        },
    )

    response = await client.get("/cabinet/jobs/00000000-0000-0000-0000-000000000222")

    assert response.status_code == 200
    assert "Транскрипт".encode() in response.content
    assert "Спикер 1: Привет".encode() in response.content
    assert "Спикер 2: Здравствуйте".encode() in response.content
    assert "Длительность:".encode() in response.content


@pytest.mark.asyncio
async def test_job_detail_page_shows_cancel_button_for_active_job(client) -> None:
    await login(client)

    response = await client.get(f"/cabinet/jobs/{TEST_ACTIVE_JOB_ID.value}")

    assert response.status_code == 200
    assert "Отменить задачу".encode() in response.content
    assert "Отменить задачу?".encode() in response.content
    assert "Да".encode() in response.content
    assert "Нет".encode() in response.content
    assert "10 сек".encode() in response.content
    assert b"job-header" in response.content
    assert b"open-cancel-job-dialog" in response.content
    assert b"sessionStorage" in response.content
    assert "/cancel".encode() in response.content


@pytest.mark.asyncio
async def test_cancel_job_post_redirects_back_to_detail(client) -> None:
    await login(client)

    response = await client.post(
        f"/cabinet/jobs/{TEST_ACTIVE_JOB_ID.value}/cancel",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/cabinet/jobs/{TEST_ACTIVE_JOB_ID.value}"
