import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

from bot.logging_utils import chat_repr, user_repr

start_router = Router()
logger = logging.getLogger(__name__)


@start_router.message(CommandStart())
async def start_handler(message: Message) -> None:
    if message.from_user is not None:
        logger.info(
            "Received /start %s %s",
            chat_repr(message.chat),
            user_repr(message.from_user),
        )

    await message.answer(
        "Привет, я бот модератор!"
    )


@start_router.message(Command("help"))
async def help_handler(message: Message) -> None:
    if message.from_user is not None:
        logger.info(
            "Received /help %s %s",
            chat_repr(message.chat),
            user_repr(message.from_user),
        )

    await message.answer(
        "Я помогаю удалять спам в чатах каналов"
    )
