from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Chat, Message, User

from grotesk.presentation.bot.api_client import APIClient
from grotesk.presentation.bot.handlers import setup_all_handlers
from grotesk.presentation.bot.handlers.auth import cmd_login, cmd_register, get_user_id, user_sessions
from grotesk.presentation.bot.handlers.balance import cmd_balance, cmd_topup
from grotesk.presentation.bot.handlers.history import cmd_history_requests, cmd_history_transactions
from grotesk.presentation.bot.handlers.predict import cmd_transcribe, cmd_video_edit


@pytest.fixture
def mock_message():
    message = AsyncMock(spec=Message)
    message.from_user = User(id=7, is_bot=False, first_name="Test")
    message.chat = Chat(id=7, type="private")
    message.answer = AsyncMock()
    return message


@pytest.fixture(autouse=True)
def clear_sessions():
    user_sessions.clear()
    yield
    user_sessions.clear()


@pytest.mark.asyncio
async def test_auth_handlers_usage_and_errors(mock_message):
    api_client = MagicMock()
    api_client.register = AsyncMock(side_effect=RuntimeError("boom"))
    api_client.login = AsyncMock(side_effect=RuntimeError("boom"))

    mock_message.text = "/register only-email"
    await cmd_register(mock_message, api_client)
    assert "Usage: /register" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/register a@b p"
    await cmd_register(mock_message, api_client)
    assert "Registration failed" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/login only-email"
    await cmd_login(mock_message, api_client)
    assert "Usage: /login" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/login a@b p"
    await cmd_login(mock_message, api_client)
    assert "Login failed" in mock_message.answer.call_args[0][0]
    assert get_user_id(7) is None


@pytest.mark.asyncio
async def test_balance_handlers_negative_paths(mock_message):
    api_client = MagicMock()
    api_client.get_balance = AsyncMock(side_effect=RuntimeError("nope"))
    api_client.top_up = AsyncMock(side_effect=RuntimeError("nope"))

    await cmd_balance(mock_message, api_client)
    assert "Please login first" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/topup 10"
    await cmd_topup(mock_message, api_client)
    assert "Please login first" in mock_message.answer.call_args[0][0]

    user_sessions[7] = "u7"
    mock_message.answer.reset_mock()
    await cmd_balance(mock_message, api_client)
    assert "Failed to get balance" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/topup"
    await cmd_topup(mock_message, api_client)
    assert "Usage: /topup" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/topup abc"
    await cmd_topup(mock_message, api_client)
    assert "Invalid amount." in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/topup 10"
    await cmd_topup(mock_message, api_client)
    assert "Failed to top up" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_predict_and_history_handlers_paths(mock_message):
    api_client = MagicMock()
    api_client.submit_transcription = AsyncMock(side_effect=RuntimeError("bad"))
    api_client.submit_video_editing = AsyncMock(side_effect=RuntimeError("bad"))
    api_client.get_transactions = AsyncMock(side_effect=RuntimeError("bad"))
    api_client.get_requests = AsyncMock(side_effect=RuntimeError("bad"))

    await cmd_transcribe(mock_message, api_client)
    assert "Please login first" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    await cmd_video_edit(mock_message, api_client)
    assert "Please login first" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    await cmd_history_transactions(mock_message, api_client)
    assert "Please login first" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    await cmd_history_requests(mock_message, api_client)
    assert "Please login first" in mock_message.answer.call_args[0][0]

    user_sessions[7] = "u7"
    mock_message.answer.reset_mock()
    mock_message.text = "/transcribe only-asset"
    await cmd_transcribe(mock_message, api_client)
    assert "Usage: /transcribe" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/transcribe a m"
    await cmd_transcribe(mock_message, api_client)
    assert "Failed to submit job" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/video_edit a m"
    await cmd_video_edit(mock_message, api_client)
    assert "Usage: /video_edit" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    mock_message.text = "/video_edit a m do this"
    await cmd_video_edit(mock_message, api_client)
    assert "Failed to submit job" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    await cmd_history_transactions(mock_message, api_client)
    assert "Failed to get history" in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    await cmd_history_requests(mock_message, api_client)
    assert "Failed to get history" in mock_message.answer.call_args[0][0]

    api_client.get_transactions = AsyncMock(return_value=[])
    api_client.get_requests = AsyncMock(return_value=[])

    mock_message.answer.reset_mock()
    await cmd_history_transactions(mock_message, api_client)
    assert "No transactions found." in mock_message.answer.call_args[0][0]

    mock_message.answer.reset_mock()
    await cmd_history_requests(mock_message, api_client)
    assert "No requests found." in mock_message.answer.call_args[0][0]

    api_client.get_transactions = AsyncMock(return_value=[{"created_at": "d", "type": "top_up", "amount": "1"}])
    api_client.get_requests = AsyncMock(return_value=[{"created_at": "d", "type": "t", "status": "done"}])
    mock_message.answer.reset_mock()
    await cmd_history_transactions(mock_message, api_client)
    assert "Transaction History" in mock_message.answer.call_args[0][0]
    mock_message.answer.reset_mock()
    await cmd_history_requests(mock_message, api_client)
    assert "Request History" in mock_message.answer.call_args[0][0]


def test_setup_all_handlers_includes_routers():
    dispatcher = MagicMock()
    setup_all_handlers(dispatcher)
    assert dispatcher.include_router.call_count == 4


@pytest.mark.asyncio
async def test_api_client_methods(monkeypatch):
    class _Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None, params=None):
            if url.endswith("/auth/register"):
                return _Response({"user_id": "u1"})
            if url.endswith("/auth/login"):
                return _Response({"user_id": "u2"})
            if url.endswith("/balance/top-up"):
                return _Response({"request_id": "r1"})
            if url.endswith("/predict/transcription"):
                return _Response({"job_id": "j1"})
            if url.endswith("/predict/video-editing"):
                return _Response({"job_id": "j2"})
            raise AssertionError(url)

        async def get(self, url, params=None):
            if url.endswith("/balance"):
                return _Response({"balance": 10.5})
            if url.endswith("/history/transactions"):
                return _Response([{"id": "1"}])
            if url.endswith("/history/requests"):
                return _Response([{"id": "2"}])
            raise AssertionError(url)

    monkeypatch.setattr("grotesk.presentation.bot.api_client.httpx.AsyncClient", _Client)
    client = APIClient("http://example.com/")
    assert client.base_url == "http://example.com"
    assert await client.register("a@b", "p") == "u1"
    assert await client.login("a@b", "p") == "u2"
    assert await client.get_balance("u") == 10.5
    assert await client.top_up("u", 5.0) == "r1"
    assert await client.submit_transcription("u", "m", "model") == "j1"
    assert await client.submit_video_editing("u", "m", "model", "prompt", operations=None) == "j2"
    assert await client.get_transactions("u") == [{"id": "1"}]
    assert await client.get_requests("u") == [{"id": "2"}]
