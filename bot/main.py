import asyncio
from aiogram import Bot, Dispatcher
from config import config
from handlers.start import start_router

async def main() -> None:
    bot = Bot(token=config.telegram_token)
    dp = Dispatcher()
    dp.include_router(start_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
