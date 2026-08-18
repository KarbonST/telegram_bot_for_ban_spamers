import asyncio
from aiogram import Bot, Dispatcher

from bot.config import config
from bot.database.session import init_db
from bot.handlers.access import access_router
from bot.handlers.start import start_router
from bot.handlers.verification import verification_router

async def main() -> None:
    await init_db()

    bot = Bot(token=config.telegram_token)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(access_router)
    dp.include_router(verification_router)

    #dp.include_router(moderation_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
