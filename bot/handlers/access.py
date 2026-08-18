from aiogram import Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import ChatMemberUpdated

from bot.config import config


access_router = Router()


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
        return

    if event.new_chat_member.status in {
        ChatMemberStatus.LEFT,
        ChatMemberStatus.KICKED,
    }:
        return

    await event.bot.leave_chat(event.chat.id)
