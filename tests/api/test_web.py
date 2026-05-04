import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from grotesk.application.processing.dto import JobHistoryItemDTO, ProcessingJobDTO
from grotesk.domain.processing.model import JobId, JobType, ProcessingStatus
from grotesk.presentation.api.dependencies import get_application
from grotesk.presentation.api.main import create_app
from grotesk.presentation.api.routers import auth
from grotesk.presentation.web import routes
from tests.api.conftest import TEST_ACTIVE_JOB_ID, MockApplication


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


class ManyJobsApplication(MockApplication):
    async def __call__(self, command_or_query):
        if type(command_or_query).__name__ == "GetUserJobHistory":
            return [
                ProcessingJobDTO(
                    job_id=JobId(UUID(f"00000000-0000-0000-0000-{index + 1:012d}")),
                    job_type=JobType.TRANSCRIPTION,
                    status=ProcessingStatus.COMPLETED,
                    created_at=datetime.now(UTC),
                    source_filename=f"job-file-{index}.wav",
                    model_name="openai/whisper-large-v3-turbo",
                    history=[JobHistoryItemDTO(status=ProcessingStatus.COMPLETED, message="done")],
                )
                for index in range(12)
            ]
        return await super().__call__(command_or_query)


def build_many_jobs_client() -> AsyncClient:
    app = create_app()
    application = ManyJobsApplication()

    async def override_get_application():
        return application

    app.dependency_overrides[get_application] = override_get_application  # type: ignore
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_home_page_renders(client) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "Grotesk".encode() in response.content


@pytest.mark.asyncio
async def test_register_and_login_pages_render_for_guest(client) -> None:
    register_response = await client.get("/register")
    login_response = await client.get("/login")
    assert register_response.status_code == 200
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_register_and_login_pages_redirect_for_logged_user(client) -> None:
    await login(client)
    register_response = await client.get("/register", follow_redirects=False)
    login_response = await client.get("/login", follow_redirects=False)
    assert register_response.status_code == 303
    assert register_response.headers["location"] == "/cabinet"
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/cabinet"


@pytest.mark.asyncio
async def test_register_submit_validation_error_renders_template(client) -> None:
    original_hash = auth.get_password_hash
    auth.get_password_hash = lambda p: "hashed_" + p
    try:
        response = await client.post("/register", data={"email": "exist@example.com", "password": "password123"})
    finally:
        auth.get_password_hash = original_hash
    assert response.status_code == 400
    assert "User already exists".encode() in response.content


@pytest.mark.asyncio
async def test_login_submit_invalid_credentials_renders_template(client) -> None:
    response = await client.post("/login", data={"email": "wrong@example.com", "password": "password123"})
    assert response.status_code == 401
    assert "Неверный email или пароль".encode() in response.content


@pytest.mark.asyncio
async def test_logout_redirects_to_home(client) -> None:
    await login(client)
    response = await client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


@pytest.mark.asyncio
async def test_balance_and_history_redirects_when_not_logged_in(client) -> None:
    balance_response = await client.get("/cabinet/balance", follow_redirects=False)
    history_response = await client.get("/cabinet/history", follow_redirects=False)
    assert balance_response.status_code == 303
    assert balance_response.headers["location"] == "/login"
    assert history_response.status_code == 303
    assert history_response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_balance_submit_error_renders_template(client) -> None:
    await login(client)
    response = await client.post("/cabinet/balance", data={"amount": "-5"})
    assert response.status_code == 400
    assert "Money amount must be non-negative".encode() in response.content


@pytest.mark.asyncio
async def test_transcription_and_video_pages_redirect_when_not_logged_in(client) -> None:
    tr = await client.get("/cabinet/transcription", follow_redirects=False)
    ve = await client.get("/cabinet/video-editing", follow_redirects=False)
    assert tr.status_code == 303
    assert tr.headers["location"] == "/login"
    assert ve.status_code == 303
    assert ve.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_transcription_submit_redirects_when_not_logged_in(client) -> None:
    response = await client.post(
        "/cabinet/transcription",
        data={"model_id": "00000000-0000-0000-0000-000000000333"},
        files={"file": ("sample.wav", io.BytesIO(b"audio-bytes"), "audio/wav")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_video_editing_submit_validation_paths(client) -> None:
    await login(client)
    common = {"model_id": "00000000-0000-0000-0000-000000000333"}
    upload = {"file": ("sample.mp4", io.BytesIO(b"video-bytes"), "video/mp4")}

    bad_ops = await client.post(
        "/cabinet/video-editing",
        data={**common, "prompt_text": "", "operations_text": "bad"},
        files=upload,
    )
    assert bad_ops.status_code == 400
    assert "используйте формат".encode() in bad_ops.content

    no_prompt = await client.post(
        "/cabinet/video-editing",
        data={**common, "prompt_text": " ", "operations_text": ""},
        files=upload,
    )
    assert no_prompt.status_code == 400
    assert "Укажите общий prompt".encode() in no_prompt.content


@pytest.mark.asyncio
async def test_video_editing_submit_errors_for_non_video_and_submit_failure(client, monkeypatch) -> None:
    await login(client)

    class _Asset:
        def __init__(self, media_type):
            self.id = type("AID", (), {"value": UUID("00000000-0000-0000-0000-000000000400")})()
            self.media_type = media_type

    monkeypatch.setattr(routes, "register_uploaded_media", AsyncMock(return_value=_Asset("audio")))
    non_video = await client.post(
        "/cabinet/video-editing",
        data={"model_id": "00000000-0000-0000-0000-000000000333", "prompt_text": "edit", "operations_text": ""},
        files={"file": ("sample.wav", io.BytesIO(b"audio"), "audio/wav")},
    )
    assert non_video.status_code == 400
    assert "нужно загрузить видеофайл".encode() in non_video.content

    monkeypatch.setattr(routes, "register_uploaded_media", AsyncMock(return_value=_Asset("video")))
    failed = await client.post(
        "/cabinet/video-editing",
        data={"model_id": "00000000-0000-0000-0000-000000000333", "prompt_text": "edit", "operations_text": ""},
        files={"file": ("sample.mp4", io.BytesIO(b"video"), "video/mp4")},
    )
    assert failed.status_code == 400
    assert "Invalid asset".encode() in failed.content


@pytest.mark.asyncio
async def test_job_detail_and_cancel_redirect_branches(client) -> None:
    not_logged_in_detail = await client.get(
        "/cabinet/jobs/00000000-0000-0000-0000-000000000222", follow_redirects=False
    )
    not_logged_in_cancel = await client.post(
        "/cabinet/jobs/00000000-0000-0000-0000-000000000222/cancel",
        follow_redirects=False,
    )
    assert not_logged_in_detail.status_code == 303
    assert not_logged_in_detail.headers["location"] == "/login"
    assert not_logged_in_cancel.status_code == 303
    assert not_logged_in_cancel.headers["location"] == "/login"

    await login(client)
    missing_job_detail = await client.get("/cabinet/jobs/00000000-0000-0000-0000-000000000999", follow_redirects=False)
    assert missing_job_detail.status_code == 303
    assert missing_job_detail.headers["location"] == "/cabinet/history"

    missing_job_cancel = await client.post(
        "/cabinet/jobs/00000000-0000-0000-0000-000000000999/cancel",
        follow_redirects=False,
    )
    assert missing_job_cancel.status_code == 303
    assert missing_job_cancel.headers["location"] == "/cabinet/jobs/00000000-0000-0000-0000-000000000999"


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
async def test_cabinet_page_defaults_to_ten_recent_jobs() -> None:
    async with build_many_jobs_client() as client:
        await login(client)
        response = await client.get("/cabinet")

    assert response.status_code == 200
    assert "Показано 10 из 12 задач.".encode() in response.content
    assert b'<option value="10" selected' in response.content
    assert "1 / 2".encode() in response.content
    assert b'aria-disabled="true"' in response.content
    assert b"/cabinet?job_limit=10&job_page=2" in response.content
    assert "job-file-0.wav".encode() in response.content
    assert "job-file-9.wav".encode() in response.content
    assert "job-file-10.wav".encode() not in response.content
    assert "job-file-11.wav".encode() not in response.content


@pytest.mark.asyncio
async def test_cabinet_page_applies_selected_job_limit() -> None:
    async with build_many_jobs_client() as client:
        await login(client)
        response = await client.get("/cabinet?job_limit=5")

    assert response.status_code == 200
    assert "Показано 5 из 12 задач.".encode() in response.content
    assert b'<option value="5" selected' in response.content
    assert "job-file-0.wav".encode() in response.content
    assert "job-file-4.wav".encode() in response.content
    assert "job-file-5.wav".encode() not in response.content


@pytest.mark.asyncio
async def test_cabinet_page_applies_selected_job_page() -> None:
    async with build_many_jobs_client() as client:
        await login(client)
        response = await client.get("/cabinet?job_limit=5&job_page=2")

    assert response.status_code == 200
    assert "Показано 5 из 12 задач.".encode() in response.content
    assert "2 / 3".encode() in response.content
    assert b"/cabinet?job_limit=5&job_page=1" in response.content
    assert b"/cabinet?job_limit=5&job_page=3" in response.content
    assert "job-file-4.wav".encode() not in response.content
    assert "job-file-5.wav".encode() in response.content
    assert "job-file-9.wav".encode() in response.content
    assert "job-file-10.wav".encode() not in response.content


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
async def test_job_detail_page_shows_filename_duration_and_time(client, monkeypatch) -> None:
    await login(client)
    monkeypatch.setattr(routes, "probe_media_duration_seconds", lambda _storage_key: 125.0)

    response = await client.get("/cabinet/jobs/00000000-0000-0000-0000-000000000222")

    assert response.status_code == 200
    assert "Файл:".encode() in response.content
    assert "sample.wav".encode() in response.content
    assert "Длительность:".encode() in response.content
    assert "2 мин 5 сек".encode() in response.content
    assert "Время:".encode() in response.content
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
