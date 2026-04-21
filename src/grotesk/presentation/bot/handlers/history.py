from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from grotesk.presentation.bot.api_client import APIClient
from grotesk.presentation.bot.handlers.auth import get_user_id

router = Router()


@router.message(Command("history_transactions"))
async def cmd_history_transactions(message: Message, api_client: APIClient) -> None:
    user_id = get_user_id(message.from_user.id)
    if not user_id:
        await message.answer("Please login first: /login <email> <password>")
        return

    try:
        transactions = await api_client.get_transactions(user_id)
        if not transactions:
            await message.answer("No transactions found.")
            return

        text = "Transaction History:\n"
        for t in transactions:
            text += f"- {t['created_at']}: {t['type']} {t['amount']}\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"Failed to get history: {e}")


@router.message(Command("history_requests"))
async def cmd_history_requests(message: Message, api_client: APIClient) -> None:
    user_id = get_user_id(message.from_user.id)
    if not user_id:
        await message.answer("Please login first: /login <email> <password>")
        return

    try:
        requests = await api_client.get_requests(user_id)
        if not requests:
            await message.answer("No requests found.")
            return

        text = "Request History:\n"
        for r in requests:
            text += f"- {r['created_at']}: {r['type']} ({r['status']})\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"Failed to get history: {e}")


def setup_history_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)
