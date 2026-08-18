import asyncio
import logging
from aiogram import Bot, Dispatcher

from bot.config import config
from bot.database.session import init_db
from bot.handlers.access import access_router
from bot.handlers.start import start_router
from bot.handlers.verification import verification_router


logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


async def main() -> None:
    setup_logging()
    logger.info(
        "Starting bot allowed_chat_id=%s verification_timeout_seconds=%s",
        config.allowed_chat_id,
        config.verification_timeout_seconds,
    )

    await init_db()
    logger.info("Database initialized")

    bot = Bot(token=config.telegram_token)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(access_router)
    dp.include_router(verification_router)
    logger.info("Enabled routers: start, access, verification")

    #dp.include_router(moderation_router)
    logger.info("Message moderation router is disabled")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
