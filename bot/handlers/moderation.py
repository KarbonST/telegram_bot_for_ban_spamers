import logging
from aiogram import Router, F
from aiogram.types import Message

from bot.logging_utils import chat_repr, text_preview, user_repr
from bot.services.verification import ensure_verification

moderation_router = Router()
logger = logging.getLogger(__name__)
FIRST_MESSAGE_VERIFICATION_TEXT = (
    "Для защиты чата нужно пройти быструю проверку. "
    "Подтвердите, что вы не бот, в течение 30 секунд."
)


@moderation_router.message()
async def moderation_handler(message: Message) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        return

    if message.new_chat_members:
        return

    if message.from_user is None or message.from_user.is_bot:
        return

    logger.info(
        "Received message %s %s message_id=%s text=%r",
        chat_repr(message.chat),
        user_repr(message.from_user),
        message.message_id,
        text_preview(message.text or message.caption),
    )

    verification_started = await ensure_verification(
        bot=message.bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        message_id=message.message_id,
        source="first_message",
        verification_text=FIRST_MESSAGE_VERIFICATION_TEXT,
    )

    if verification_started:
        logger.info(
            "Verification started after first message %s %s message_id=%s",
            chat_repr(message.chat),
            user_repr(message.from_user),
            message.message_id,
        )
