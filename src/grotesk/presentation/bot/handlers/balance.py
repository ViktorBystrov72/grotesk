from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from grotesk.presentation.bot.api_client import APIClient
from grotesk.presentation.bot.handlers.auth import get_user_id

router = Router()


@router.message(Command("balance"))
async def cmd_balance(message: Message, api_client: APIClient) -> None:
    user_id = get_user_id(message.from_user.id)
    if not user_id:
        await message.answer("Please login first: /login <email> <password>")
        return

    try:
        balance = await api_client.get_balance(user_id)
        await message.answer(f"Your current balance is: {balance}")
    except Exception as e:
        await message.answer(f"Failed to get balance: {e}")


@router.message(Command("topup"))
async def cmd_topup(message: Message, api_client: APIClient) -> None:
    user_id = get_user_id(message.from_user.id)
    if not user_id:
        await message.answer("Please login first: /login <email> <password>")
        return

    args = message.text.split()[1:] if message.text else []
    if len(args) != 1:
        await message.answer("Usage: /topup <amount>")
        return

    try:
        amount = float(args[0])
        request_id = await api_client.top_up(user_id, amount)
        await message.answer(f"Top-up request created. Request ID: {request_id}")
    except ValueError:
        await message.answer("Invalid amount.")
    except Exception as e:
        await message.answer(f"Failed to top up: {e}")


def setup_balance_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)
