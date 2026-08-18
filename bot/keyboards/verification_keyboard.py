from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def verification_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"verify_user:{user_id}"
                )
            ]
        ]
    )
