from aiogram import Router, F
from aiogram.types import Message

from bot.services.verification import ensure_verification

moderation_router = Router()


@moderation_router.message()
async def moderation_handler(message: Message) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        return

    if message.new_chat_members:
        return

    if message.from_user is None or message.from_user.is_bot:
        return

    should_block_user = await ensure_verification(
        bot=message.bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        message_id=message.message_id,
    )

    if should_block_user:
        await message.delete()
