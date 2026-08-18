import logging
from aiogram import Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import ChatMemberUpdated

from bot.config import config
from bot.logging_utils import chat_repr, user_repr


access_router = Router()
logger = logging.getLogger(__name__)


@access_router.my_chat_member()
async def restrict_bot_access(event: ChatMemberUpdated) -> None:
    if config.allowed_chat_id is None:
        return

    if event.chat.type not in {
        ChatType.GROUP,
        ChatType.SUPERGROUP,
        ChatType.CHANNEL,
    }:
        return

    if event.chat.id == config.allowed_chat_id:
        logger.info(
            "Bot access accepted %s invited_by=%s new_status=%s",
            chat_repr(event.chat),
            user_repr(event.from_user),
            event.new_chat_member.status,
        )
        return

    if event.new_chat_member.status in {
        ChatMemberStatus.LEFT,
        ChatMemberStatus.KICKED,
    }:
        return

    logger.warning(
        "Bot access rejected %s invited_by=%s allowed_chat_id=%s new_status=%s",
        chat_repr(event.chat),
        user_repr(event.from_user),
        config.allowed_chat_id,
        event.new_chat_member.status,
    )
    await event.bot.leave_chat(event.chat.id)
