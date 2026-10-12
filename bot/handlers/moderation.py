import logging

from aiogram import Router
from aiogram.types import Message

from bot.config import config
from bot.logging_utils import chat_repr, text_preview, user_repr
from bot.services.spam_moderation import moderate_message_for_spam
from bot.services.verification import ensure_verification

moderation_router = Router()
logger = logging.getLogger(__name__)
FIRST_MESSAGE_VERIFICATION_TEXT = (
    "Для защиты чата нужно пройти быструю проверку. "
    "Подтвердите, что вы не бот, в течение 30 секунд."
)


@moderation_router.message()
async def moderation_handler(message: Message) -> None:
    if not _is_moderatable_message(message, update_type="message"):
        return

    logger.info(
        "Received message %s %s message_id=%s text=%r",
        chat_repr(message.chat),
        user_repr(message.from_user),
        message.message_id,
        text_preview(message.text or message.caption),
    )

    if await _process_spam_moderation(message, update_type="message"):
        return

    if not config.first_message_verification_enabled:
        logger.info(
            "Skipping first-message verification by config %s %s message_id=%s mode=%s",
            chat_repr(message.chat),
            user_repr(message.from_user),
            message.message_id,
            config.message_moderation_mode,
        )
        return

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


@moderation_router.edited_message()
async def edited_message_moderation_handler(message: Message) -> None:
    if not _is_moderatable_message(message, update_type="edited_message"):
        return

    logger.info(
        "Received edited message %s %s message_id=%s edit_date=%s text=%r",
        chat_repr(message.chat),
        user_repr(message.from_user),
        message.message_id,
        message.edit_date.isoformat() if message.edit_date else None,
        text_preview(message.text or message.caption),
    )

    await _process_spam_moderation(message, update_type="edited_message")


def _is_moderatable_message(message: Message, *, update_type: str) -> bool:
    if message.chat.type not in {"group", "supergroup"}:
        return False

    if message.new_chat_members:
        return False

    if message.sender_chat is not None:
        logger.info(
            "Skipping %s sent on behalf of chat %s sender_chat=%s message_id=%s",
            update_type,
            chat_repr(message.chat),
            chat_repr(message.sender_chat),
            message.message_id,
        )
        return False

    if message.is_automatic_forward:
        logger.info(
            "Skipping automatic forward update_type=%s %s message_id=%s",
            update_type,
            chat_repr(message.chat),
            message.message_id,
        )
        return False

    if message.from_user is None or message.from_user.is_bot:
        return False

    return True


async def _process_spam_moderation(
    message: Message,
    *,
    update_type: str,
) -> bool:
    if config.gigachat_spam_moderation_enabled:
        spam_result = await moderate_message_for_spam(message)

        if spam_result.action != "allow":
            logger.info(
                "Message processing stopped after spam moderation update_type=%s "
                "%s %s message_id=%s action=%s score=%s",
                update_type,
                chat_repr(message.chat),
                user_repr(message.from_user),
                message.message_id,
                spam_result.action,
                spam_result.score,
            )
            return True
    else:
        logger.info(
            "Skipping GigaChat spam moderation by config update_type=%s "
            "%s %s message_id=%s mode=%s",
            update_type,
            chat_repr(message.chat),
            user_repr(message.from_user),
            message.message_id,
            config.message_moderation_mode,
        )

    return False
