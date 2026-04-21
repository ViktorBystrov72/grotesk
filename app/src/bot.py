import asyncio
import logging

from grotesk.presentation.bot.handlers import setup_all_handlers
from grotesk.presentation.bot.main import create_bot

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    bot, dp, api_client = create_bot()
    setup_all_handlers(dp)

    logging.info("Starting Telegram Bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
