from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.services.verification import confirm_verification, ensure_verification

verification_router = Router()


@verification_router.message(F.new_chat_members)
async def verify_new_chat_members(message: Message) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        return

    for new_member in message.new_chat_members or []:
        if new_member.is_bot:
            continue

        await ensure_verification(
            bot=message.bot,
            chat_id=message.chat.id,
            user_id=new_member.id,
        )


@verification_router.callback_query(F.data.startswith("verify_user:"))
async def verify_user(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    user_id = int(callback.data.split(":", 1)[1])

    if callback.from_user.id != user_id:
        await callback.answer("Эта кнопка не для вас", show_alert=True)
        return

    verified = await confirm_verification(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user_id=user_id,
    )

    if verified:
        await callback.answer("Проверка пройдена")
        return

    await callback.answer("Проверка уже завершена", show_alert=True)
