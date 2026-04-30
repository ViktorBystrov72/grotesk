from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from grotesk.application.identity_access.dto import UserDTO
from grotesk.domain.identity_access.model import UserId, UserRole
from grotesk.presentation.api import contracts, dependencies
from grotesk.presentation.api.main import create_app
from grotesk.presentation.api.routers import auth
from tests.api.conftest import TEST_USER_ID


def test_contracts_dataclasses_default_and_frozen() -> None:
    upload = contracts.UploadMediaRequest(media_type="audio", file_name="a.wav")
    assert upload.prompt_attachments == []

    timeline = contracts.TimelineOperationRequest(start_second=0, end_second=1, prompt="p")
    submit = contracts.SubmitVideoEditingRequest(
        media_asset_id="m",
        model_id="model",
        prompt_text="t",
        operations=[timeline],
    )
    assert submit.operations[0].prompt == "p"
    assert contracts.SubmitTranscriptionRequest(media_asset_id="m", model_id="model").media_asset_id == "m"
    assert contracts.RegisterUserRequest(email="e@x", password="p").email == "e@x"
    assert contracts.ApproveTopUpRequest(request_id="r").request_id == "r"

    with pytest.raises(FrozenInstanceError):
        upload.file_name = "b.wav"  # type: ignore[misc]


def test_auth_password_helpers_cover_all_branches() -> None:
    assert auth._password_bytes("x" * 100) == ("x" * 72).encode("utf-8")
    assert auth.verify_password("plain", "") is False
    assert auth.verify_password("plain", "not-bcrypt") is False
    assert isinstance(auth.get_password_hash("plain"), str)
    assert auth.get_password_hash("plain").startswith("$2")


def test_auth_verify_password_handles_bcrypt_exceptions(monkeypatch) -> None:
    def _raise_value_error(*_args, **_kwargs):
        raise ValueError("bad hash")

    monkeypatch.setattr(auth.bcrypt, "checkpw", _raise_value_error)
    assert auth.verify_password("plain", "$2b$12$abcdefghijklmnopqrstuv") is False

    def _raise_type_error(*_args, **_kwargs):
        raise TypeError("bad input")

    monkeypatch.setattr(auth.bcrypt, "checkpw", _raise_type_error)
    assert auth.verify_password("plain", "$2b$12$abcdefghijklmnopqrstuv") is False


@pytest.mark.asyncio
async def test_dependencies_get_session_and_get_application(monkeypatch) -> None:
    session_obj = object()

    @asynccontextmanager
    async def session_factory():
        yield session_obj

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=session_factory)))
    collected_sessions: list[object] = []
    monkeypatch.setattr(
        dependencies,
        "build_application",
        lambda s: collected_sessions.append(s) or SimpleNamespace(name="app"),
    )

    yielded = []
    async for s in dependencies.get_session(request):
        yielded.append(s)
    assert yielded == [session_obj]

    built = await dependencies.get_application(session_obj)  # type: ignore[arg-type]
    assert built.name == "app"
    assert collected_sessions == [session_obj]


@pytest.mark.asyncio
async def test_dependencies_current_user_and_resolution_branches() -> None:
    request_no_user = SimpleNamespace(session={})
    current_none = await dependencies.get_optional_current_user(request_no_user, application=SimpleNamespace())
    assert current_none is None

    user = UserDTO(
        user_id=TEST_USER_ID,
        email="test@example.com",
        password_hash="h",
        role=UserRole.CUSTOMER,
        is_active=True,
    )

    async def _ok(_query):
        return user

    app_ok = SimpleNamespace(get_user_by_id=_ok)
    request_with_user = SimpleNamespace(session={dependencies.SESSION_USER_ID_KEY: str(TEST_USER_ID.value)})
    assert await dependencies.get_optional_current_user(request_with_user, application=app_ok) == user

    async def _fail(_query):
        raise ValueError("boom")

    app_fail = SimpleNamespace(get_user_by_id=_fail)
    request_invalid = SimpleNamespace(session={dependencies.SESSION_USER_ID_KEY: "broken"})
    assert await dependencies.get_optional_current_user(request_invalid, application=app_fail) is None
    assert request_invalid.session == {}

    assert await dependencies.get_current_user(user) == user
    with pytest.raises(HTTPException):
        await dependencies.get_current_user(None)

    explicit = dependencies.resolve_user_id(UUID("00000000-0000-0000-0000-000000000123"), current_user=None)
    assert isinstance(explicit, UserId)
    assert dependencies.resolve_user_id(None, current_user=user) == user.user_id


@pytest.mark.asyncio
async def test_exception_handlers_cover_value_error_and_unhandled_exception() -> None:
    app = create_app()

    @app.get("/_raise_value_error")
    async def _raise_value_error() -> dict[str, str]:
        raise ValueError("bad")

    @app.get("/_raise_runtime_error")
    async def _raise_runtime_error() -> dict[str, str]:
        raise RuntimeError("bad")

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        value_error_response = await client.get("/_raise_value_error")
        runtime_error_response = await client.get("/_raise_runtime_error")

    assert value_error_response.status_code == 400
    assert value_error_response.json()["detail"] == "bad"
    assert runtime_error_response.status_code == 500
    assert runtime_error_response.json()["detail"] == "Internal server error"
