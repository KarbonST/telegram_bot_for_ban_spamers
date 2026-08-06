import asyncio
from aiogram import Bot, Dispatcher, html
from config import config

async def main() -> None:
    bot = Bot(token=config.telegram_token)
    dp = Dispatcher()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())