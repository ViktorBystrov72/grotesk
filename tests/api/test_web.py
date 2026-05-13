import io
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from grotesk.application.processing.dto import JobHistoryItemDTO, ProcessingJobDTO
from grotesk.domain.processing.model import JobId, JobType, ProcessingStatus
from grotesk.presentation.api.dependencies import get_application
from grotesk.presentation.api.main import create_app
from grotesk.presentation.api.routers import auth
from grotesk.presentation.api.routers import jobs as jobs_router_module
from grotesk.presentation.web import routes
from tests.api.conftest import TEST_ACTIVE_JOB_ID, TEST_VIDEO_DETAIL_JOB_ID, MockApplication


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
async def test_video_editing_page_selects_decart_model_by_default(client, monkeypatch) -> None:
    monkeypatch.delenv("HF_VIDEO_MODEL_ID", raising=False)
    await login(client)
    response = await client.get("/cabinet/video-editing")
    assert response.status_code == 200
    needle = b"00000000-0000-0000-0000-000000000444"
    assert needle in response.content
    pos = response.content.find(needle)
    assert response.content[pos : pos + 200].find(b"selected") >= 0


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
    assert "Исходное аудио".encode() in response.content
    assert b"/cabinet/jobs/00000000-0000-0000-0000-000000000222/source-audio" in response.content
    assert b"<audio " in response.content
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
async def test_job_source_audio_requires_login(client) -> None:
    response = await client.get(
        "/cabinet/jobs/00000000-0000-0000-0000-000000000222/source-audio",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_job_detail_page_shows_video_previews_after_progress(client, tmp_path, monkeypatch) -> None:
    await login(client)
    out_mp4 = tmp_path / "out.mp4"
    out_mp4.write_bytes(b"fake-video")
    monkeypatch.setattr(routes, "resolve_result_artifact_path", lambda *args, **kwargs: out_mp4)

    response = await client.get(f"/cabinet/jobs/{TEST_VIDEO_DETAIL_JOB_ID.value}")

    assert response.status_code == 200
    assert "Видео".encode() in response.content
    assert "Исходное видео".encode() in response.content
    assert "Результат".encode() in response.content
    assert response.content.lower().find(b"<video") >= 0
    artifact_path = f"/jobs/{TEST_VIDEO_DETAIL_JOB_ID.value}/artifact".encode()
    assert artifact_path in response.content


@pytest.mark.asyncio
async def test_job_source_video_requires_login(client) -> None:
    response = await client.get(
        f"/cabinet/jobs/{TEST_VIDEO_DETAIL_JOB_ID.value}/source-video",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_job_source_video_404_for_transcription_job(client) -> None:
    await login(client)
    response = await client.get("/cabinet/jobs/00000000-0000-0000-0000-000000000222/source-video")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_job_source_video_streams_file_for_logged_user(client) -> None:
    await login(client)
    response = await client.get(f"/cabinet/jobs/{TEST_VIDEO_DETAIL_JOB_ID.value}/source-video")
    assert response.status_code == 200
    ct = response.headers.get("content-type", "")
    assert ct.startswith("video/") or "application/octet-stream" in ct
    assert response.content == b"fake-mp4"


@pytest.mark.asyncio
async def test_job_artifact_mp4_returns_video_media_type(client, tmp_path, monkeypatch) -> None:
    await login(client)
    out_mp4 = tmp_path / "result.mp4"
    out_mp4.write_bytes(b"mp4binary")
    monkeypatch.setattr(jobs_router_module, "resolve_result_artifact_path", lambda *args, **kwargs: out_mp4)

    response = await client.get(f"/jobs/{TEST_VIDEO_DETAIL_JOB_ID.value}/artifact")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("video/mp4")


@pytest.mark.asyncio
async def test_job_source_audio_streams_file_for_logged_user(client) -> None:
    await login(client)

    response = await client.get("/cabinet/jobs/00000000-0000-0000-0000-000000000222/source-audio")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("audio/")
    assert response.content == b"fake-wav"


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
