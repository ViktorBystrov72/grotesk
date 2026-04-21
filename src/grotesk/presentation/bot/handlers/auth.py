from aiogram import Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from grotesk.presentation.bot.api_client import APIClient

router = Router()

user_sessions: dict[int, str] = {}


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Welcome to Grotesk ML Media Service Bot!\n"
        "Available commands:\n"
        "/register <email> <password>\n"
        "/login <email> <password>\n"
        "/balance\n"
        "/topup <amount>\n"
        "/transcribe <media_asset_id> <model_id>\n"
        "/video_edit <media_asset_id> <model_id> <prompt>\n"
        "/history_transactions\n"
        "/history_requests"
    )


@router.message(Command("register"))
async def cmd_register(message: Message, api_client: APIClient) -> None:
    args = message.text.split()[1:] if message.text else []
    if len(args) != 2:
        await message.answer("Usage: /register <email> <password>")
        return

    email, password = args
    try:
        user_id = await api_client.register(email, password)
        user_sessions[message.from_user.id] = user_id
        await message.answer(f"Successfully registered and logged in! User ID: {user_id}")
    except Exception as e:
        await message.answer(f"Registration failed: {e}")


@router.message(Command("login"))
async def cmd_login(message: Message, api_client: APIClient) -> None:
    args = message.text.split()[1:] if message.text else []
    if len(args) != 2:
        await message.answer("Usage: /login <email> <password>")
        return

    email, password = args
    try:
        user_id = await api_client.login(email, password)
        user_sessions[message.from_user.id] = user_id
        await message.answer("Successfully logged in!")
    except Exception as e:
        await message.answer(f"Login failed: {e}")


def get_user_id(tg_user_id: int) -> str | None:
    return user_sessions.get(tg_user_id)


def setup_auth_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)
