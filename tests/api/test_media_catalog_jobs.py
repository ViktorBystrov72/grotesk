import io

import pytest

from grotesk.presentation.api.routers import auth
from grotesk.presentation.api.routers import jobs as jobs_router


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
async def test_upload_media_requires_login(client) -> None:
    response = await client.post(
        "/media/upload",
        files={"file": ("sample.wav", io.BytesIO(b"audio-bytes"), "audio/wav")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_media_unsupported_type_returns_400(client) -> None:
    await login(client)
    response = await client.post(
        "/media/upload",
        files={"file": ("notes.txt", io.BytesIO(b"text"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported media type." in response.json()["detail"]


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
async def test_job_detail_not_found_returns_404(client) -> None:
    await login(client)
    response = await client.get("/jobs/00000000-0000-0000-0000-000000000999")
    assert response.status_code == 404
    assert "Processing job does not exist." in response.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_job_success(client) -> None:
    await login(client)

    response = await client.post("/jobs/00000000-0000-0000-0000-000000000223/cancel")

    assert response.status_code == 200
    assert response.json() == {"status": "canceled"}


@pytest.mark.asyncio
async def test_cancel_job_not_found_returns_400(client) -> None:
    await login(client)
    response = await client.post("/jobs/00000000-0000-0000-0000-000000000999/cancel")
    assert response.status_code == 400
    assert "Processing job does not exist." in response.json()["detail"]


@pytest.mark.asyncio
async def test_download_job_artifact_requires_login(client) -> None:
    response = await client.get("/jobs/00000000-0000-0000-0000-000000000222/artifact")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_download_job_artifact_not_found_when_missing(client) -> None:
    await login(client)
    response = await client.get("/jobs/00000000-0000-0000-0000-000000000222/artifact")
    assert response.status_code == 404
    assert response.json()["detail"] == "Artifact not found."


@pytest.mark.asyncio
async def test_download_job_artifact_job_not_found_returns_404(client) -> None:
    await login(client)
    response = await client.get("/jobs/00000000-0000-0000-0000-000000000999/artifact")
    assert response.status_code == 404
    assert "Processing job does not exist." in response.json()["detail"]


@pytest.mark.asyncio
async def test_download_job_artifact_json_success(client, tmp_path, monkeypatch) -> None:
    await login(client)
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text('{"text": "Привет", "turns": []}', encoding="utf-8")
    monkeypatch.setattr(jobs_router, "resolve_result_artifact_path", lambda *_args, **_kwargs: artifact_path)

    response = await client.get("/jobs/00000000-0000-0000-0000-000000000222/artifact")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.content
    assert response.text
    assert response.text.find("Привет") != -1


@pytest.mark.asyncio
async def test_download_job_artifact_non_json_success_without_rewrite(client, tmp_path, monkeypatch) -> None:
    await login(client)
    artifact_path = tmp_path / "artifact.txt"
    artifact_path.write_text("raw-artifact", encoding="utf-8")
    monkeypatch.setattr(jobs_router, "resolve_result_artifact_path", lambda *_args, **_kwargs: artifact_path)

    response = await client.get("/jobs/00000000-0000-0000-0000-000000000222/artifact")

    assert response.status_code == 200
    assert "raw-artifact" in response.text


@pytest.mark.asyncio
async def test_download_job_artifact_json_with_empty_payload_skips_rewrite(client, tmp_path, monkeypatch) -> None:
    await login(client)
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text('{"text": "unchanged"}', encoding="utf-8")
    monkeypatch.setattr(jobs_router, "resolve_result_artifact_path", lambda *_args, **_kwargs: artifact_path)
    monkeypatch.setattr(jobs_router, "load_json_artifact", lambda _path: None)

    response = await client.get("/jobs/00000000-0000-0000-0000-000000000222/artifact")

    assert response.status_code == 200
    assert "unchanged" in artifact_path.read_text(encoding="utf-8")
