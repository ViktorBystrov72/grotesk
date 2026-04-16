import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User, Chat

from grotesk.presentation.bot.api_client import APIClient
from grotesk.presentation.bot.handlers.auth import cmd_start, cmd_register, cmd_login, user_sessions
from grotesk.presentation.bot.handlers.balance import cmd_balance, cmd_topup
from grotesk.presentation.bot.handlers.predict import cmd_transcribe, cmd_video_edit


@pytest.fixture
def mock_api_client():
    client = MagicMock(spec=APIClient)
    client.register = AsyncMock(return_value="user_id_123")
    client.login = AsyncMock(return_value="user_id_123")
    client.get_balance = AsyncMock(return_value=150.0)
    client.top_up = AsyncMock(return_value="req_123")
    client.submit_transcription = AsyncMock(return_value="job_123")
    client.submit_video_editing = AsyncMock(return_value="job_456")
    return client


@pytest.fixture
def mock_message():
    message = AsyncMock(spec=Message)
    message.from_user = User(id=1, is_bot=False, first_name="Test")
    message.chat = Chat(id=1, type="private")
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_cmd_start(mock_message):
    await cmd_start(mock_message)
    mock_message.answer.assert_called_once()
    assert "Welcome" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_register(mock_message, mock_api_client):
    mock_message.text = "/register test@example.com password123"
    await cmd_register(mock_message, mock_api_client)
    
    mock_api_client.register.assert_called_once_with("test@example.com", "password123")
    mock_message.answer.assert_called_once()
    assert "Successfully registered" in mock_message.answer.call_args[0][0]
    assert user_sessions[1] == "user_id_123"


@pytest.mark.asyncio
async def test_cmd_login(mock_message, mock_api_client):
    mock_message.text = "/login test@example.com password123"
    await cmd_login(mock_message, mock_api_client)
    
    mock_api_client.login.assert_called_once_with("test@example.com", "password123")
    mock_message.answer.assert_called_once()
    assert "Successfully logged in" in mock_message.answer.call_args[0][0]
    assert user_sessions[1] == "user_id_123"


@pytest.mark.asyncio
async def test_cmd_balance(mock_message, mock_api_client):
    user_sessions[1] = "user_id_123"
    await cmd_balance(mock_message, mock_api_client)
    
    mock_api_client.get_balance.assert_called_once_with("user_id_123")
    mock_message.answer.assert_called_once()
    assert "150.0" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_topup(mock_message, mock_api_client):
    user_sessions[1] = "user_id_123"
    mock_message.text = "/topup 50.0"
    await cmd_topup(mock_message, mock_api_client)
    
    mock_api_client.top_up.assert_called_once_with("user_id_123", 50.0)
    mock_message.answer.assert_called_once()
    assert "req_123" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_transcribe(mock_message, mock_api_client):
    user_sessions[1] = "user_id_123"
    mock_message.text = "/transcribe asset_1 model_1"
    await cmd_transcribe(mock_message, mock_api_client)
    
    mock_api_client.submit_transcription.assert_called_once_with("user_id_123", "asset_1", "model_1")
    mock_message.answer.assert_called_once()
    assert "job_123" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_video_edit(mock_message, mock_api_client):
    user_sessions[1] = "user_id_123"
    mock_message.text = "/video_edit asset_1 model_1 make it cooler"
    await cmd_video_edit(mock_message, mock_api_client)
    
    mock_api_client.submit_video_editing.assert_called_once_with("user_id_123", "asset_1", "model_1", "make it cooler")
    mock_message.answer.assert_called_once()
    assert "job_456" in mock_message.answer.call_args[0][0]
