import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.config import config
from bot.logging_utils import chat_repr, user_repr
from bot.services.verification import confirm_verification, ensure_verification

verification_router = Router()
logger = logging.getLogger(__name__)
JOIN_VERIFICATION_TEXT = (
    "Добро пожаловать! Подтвердите, что вы не бот, "
    "в течение 30 секунд."
)


@verification_router.message(F.new_chat_members)
async def verify_new_chat_members(message: Message) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        return

    if not config.join_verification_enabled:
        logger.info(
            "Skipping join verification by config %s new_chat_members=%s",
            chat_repr(message.chat),
            [user_repr(member) for member in message.new_chat_members or []],
        )
        return

    for new_member in message.new_chat_members or []:
        if new_member.is_bot:
            continue

        logger.info(
            "New member joined %s %s",
            chat_repr(message.chat),
            user_repr(new_member),
        )

        await ensure_verification(
            bot=message.bot,
            chat_id=message.chat.id,
            user_id=new_member.id,
            source="join",
            verification_text=JOIN_VERIFICATION_TEXT,
        )


@verification_router.callback_query(F.data.startswith("verify_user:"))
async def verify_user(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    user_id = int(callback.data.split(":", 1)[1])
    logger.info(
        "Verification button clicked chat_id=%s clicked_by=%s target_user_id=%s callback_data=%s",
        callback.message.chat.id,
        user_repr(callback.from_user),
        user_id,
        callback.data,
    )

    if callback.from_user.id != user_id:
        logger.warning(
            "Verification button denied chat_id=%s clicked_by=%s target_user_id=%s",
            callback.message.chat.id,
            user_repr(callback.from_user),
            user_id,
        )
        await callback.answer("Эта кнопка не для вас", show_alert=True)
        return

    verified = await confirm_verification(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user_id=user_id,
    )

    if verified:
        logger.info(
            "Verification confirmed chat_id=%s %s",
            callback.message.chat.id,
            user_repr(callback.from_user),
        )
        await callback.answer("Проверка пройдена")
        return

    logger.info(
        "Verification already completed chat_id=%s %s",
        callback.message.chat.id,
        user_repr(callback.from_user),
    )
    await callback.answer("Проверка уже завершена", show_alert=True)
