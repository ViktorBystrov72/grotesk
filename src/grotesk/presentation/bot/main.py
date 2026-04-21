import os

from aiogram import Bot, Dispatcher

from grotesk.presentation.bot.api_client import APIClient
from grotesk.presentation.bot.middlewares.api_client import APIClientMiddleware


def create_bot() -> tuple[Bot, Dispatcher, APIClient]:
    token = os.getenv("BOT_TOKEN", "dummy_token")
    api_url = os.getenv("API_URL", "http://localhost:8000")

    bot = Bot(token=token)
    dp = Dispatcher()
    api_client = APIClient(base_url=api_url)

    dp.update.middleware(APIClientMiddleware(api_client))

    return bot, dp, api_client
