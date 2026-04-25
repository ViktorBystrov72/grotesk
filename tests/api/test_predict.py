import pytest


@pytest.mark.asyncio
async def test_submit_transcription_success(client):
    response = await client.post(
        "/predict/transcription",
        params={"user_id": "00000000-0000-0000-0000-000000000001"},
        json={
            "media_asset_id": "00000000-0000-0000-0000-000000000002",
            "model_id": "00000000-0000-0000-0000-000000000003",
        },
    )
    assert response.status_code == 200
    assert response.json()["job_id"]


@pytest.mark.asyncio
async def test_submit_transcription_without_user_context_returns_unauthorized(client):
    response = await client.post(
        "/predict/transcription",
        json={
            "media_asset_id": "00000000-0000-0000-0000-000000000002",
            "model_id": "00000000-0000-0000-0000-000000000003",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_submit_transcription_invalid_asset(client):
    response = await client.post(
        "/predict/transcription",
        params={"user_id": "00000000-0000-0000-0000-000000000001"},
        json={
            "media_asset_id": "00000000-0000-0000-0000-000000000400",
            "model_id": "00000000-0000-0000-0000-000000000003",
        },
    )
    assert response.status_code == 400
    assert "Invalid asset" in response.json()["detail"]


@pytest.mark.asyncio
async def test_submit_transcription_invalid_uuid(client):
    response = await client.post(
        "/predict/transcription",
        params={"user_id": "00000000-0000-0000-0000-000000000001"},
        json={
            "media_asset_id": "invalid",
            "model_id": "00000000-0000-0000-0000-000000000003",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_video_editing_success(client):
    response = await client.post(
        "/predict/video-editing",
        params={"user_id": "00000000-0000-0000-0000-000000000001"},
        json={
            "media_asset_id": "00000000-0000-0000-0000-000000000002",
            "model_id": "00000000-0000-0000-0000-000000000003",
            "prompt_text": "Make it cooler",
        },
    )
    assert response.status_code == 200
    assert response.json()["job_id"]


@pytest.mark.asyncio
async def test_submit_video_editing_invalid_asset(client):
    response = await client.post(
        "/predict/video-editing",
        params={"user_id": "00000000-0000-0000-0000-000000000001"},
        json={
            "media_asset_id": "00000000-0000-0000-0000-000000000400",
            "model_id": "00000000-0000-0000-0000-000000000003",
            "prompt_text": "Make it cooler",
        },
    )
    assert response.status_code == 400
    assert "Invalid asset" in response.json()["detail"]


@pytest.mark.asyncio
async def test_submit_video_editing_invalid_uuid(client):
    response = await client.post(
        "/predict/video-editing",
        params={"user_id": "invalid"},
        json={
            "media_asset_id": "00000000-0000-0000-0000-000000000002",
            "model_id": "00000000-0000-0000-0000-000000000003",
            "prompt_text": "Make it cooler",
        },
    )
    assert response.status_code == 422
