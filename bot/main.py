import asyncio
import logging
from aiogram import Bot, Dispatcher

from bot.config import config
from bot.database.session import init_db
from bot.handlers.moderation import moderation_router
from bot.handlers.access import access_router
from bot.handlers.start import start_router
from bot.handlers.verification import verification_router
from bot.middlewares.message_audit import MessageAuditMiddleware


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
        "Starting bot allowed_chat_id=%s verification_timeout_seconds=%s "
        "first_message_verification_enabled=%s gemini_spam_moderation_enabled=%s "
        "message_moderation_mode=%s",
        config.allowed_chat_id,
        config.verification_timeout_seconds,
        config.first_message_verification_enabled,
        config.gemini_spam_moderation_enabled,
        config.message_moderation_mode,
    )

    await init_db()
    logger.info("Database initialized")

    bot = Bot(token=config.telegram_token)
    dp = Dispatcher()
    dp.message.outer_middleware(MessageAuditMiddleware())
    logger.info("Enabled middlewares: message_audit")

    dp.include_router(start_router)
    dp.include_router(access_router)
    dp.include_router(verification_router)
    dp.include_router(moderation_router)
    logger.info("Enabled routers: start, access, verification, moderation")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
