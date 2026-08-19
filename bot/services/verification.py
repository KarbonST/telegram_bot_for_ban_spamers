import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatPermissions

from bot.config import config
from bot.database.users.repository import (
    get_or_create_user,
    mark_user_verified,
)
from bot.keyboards.verification_keyboard import verification_keyboard


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PendingVerification:
    verify_message_id: int
    message_ids: set[int] = field(default_factory=set)
    task: asyncio.Task[None] | None = None


pending_verifications: dict[tuple[int, int], PendingVerification] = {}
verification_locks: dict[tuple[int, int], asyncio.Lock] = {}


async def ensure_verification(
    bot: Bot,
    chat_id: int,
    user_id: int,
    message_id: int | None = None,
    source: str = "unknown",
    verification_text: str = (
        "Подтвердите, что вы не бот, в течение 30 секунд."
    ),
) -> bool:
    key = (chat_id, user_id)
    lock = _get_lock(key)

    async with lock:
        user = await get_or_create_user(chat_id, user_id)

        if user.is_verified:
            logger.info(
                "Skip verification for verified user chat_id=%s user_id=%s",
                chat_id,
                user_id,
            )
            return False

        state = pending_verifications.get(key)

        if state is None:
            logger.info(
                "Starting verification chat_id=%s user_id=%s source=%s timeout=%s",
                chat_id,
                user_id,
                source,
                config.verification_timeout_seconds,
            )
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=_restricted_permissions(),
            )

            verification_message = await bot.send_message(
                chat_id=chat_id,
                text=verification_text,
                reply_markup=verification_keyboard(user_id),
            )

            state = PendingVerification(verify_message_id=verification_message.message_id)
            pending_verifications[key] = state
            state.task = asyncio.create_task(
                _expire_verification(bot, chat_id, user_id),
                name=f"verification:{chat_id}:{user_id}",
            )
            logger.info(
                "Verification message sent chat_id=%s user_id=%s source=%s verify_message_id=%s",
                chat_id,
                user_id,
                source,
                verification_message.message_id,
            )
        else:
            logger.info(
                "Verification already pending chat_id=%s user_id=%s source=%s verify_message_id=%s tracked_messages=%s",
                chat_id,
                user_id,
                source,
                state.verify_message_id,
                len(state.message_ids),
            )

        if message_id is not None:
            state.message_ids.add(message_id)
            logger.info(
                "Tracked message for pending verification chat_id=%s user_id=%s source=%s message_id=%s tracked_messages=%s",
                chat_id,
                user_id,
                source,
                message_id,
                len(state.message_ids),
            )

        return True


async def confirm_verification(bot: Bot, chat_id: int, user_id: int) -> bool:
    key = (chat_id, user_id)
    lock = _get_lock(key)

    async with lock:
        state = pending_verifications.pop(key, None)

        if state is None:
            logger.info(
                "Verification confirm skipped because no pending state chat_id=%s user_id=%s",
                chat_id,
                user_id,
            )
            return False

        user = await get_or_create_user(chat_id, user_id)

        if user.is_verified:
            logger.info(
                "Verification confirm skipped because user already verified chat_id=%s user_id=%s",
                chat_id,
                user_id,
            )
            return False

        if state.task:
            state.task.cancel()
            with suppress(asyncio.CancelledError):
                await state.task
            logger.info(
                "Verification timeout task cancelled chat_id=%s user_id=%s",
                chat_id,
                user_id,
            )

        await mark_user_verified(chat_id, user_id)
        logger.info(
            "User marked as verified chat_id=%s user_id=%s",
            chat_id,
            user_id,
        )

        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=await _allowed_permissions(bot, chat_id),
        )
        logger.info(
            "Chat permissions restored for verified user chat_id=%s user_id=%s",
            chat_id,
            user_id,
        )

        with suppress(TelegramBadRequest, TelegramForbiddenError):
            await bot.delete_message(chat_id, state.verify_message_id)
            logger.info(
                "Verification message deleted chat_id=%s user_id=%s verify_message_id=%s",
                chat_id,
                user_id,
                state.verify_message_id,
            )

        return True


async def _expire_verification(bot: Bot, chat_id: int, user_id: int) -> None:
    try:
        await asyncio.sleep(config.verification_timeout_seconds)
    except asyncio.CancelledError:
        return

    key = (chat_id, user_id)
    lock = _get_lock(key)

    async with lock:
        state = pending_verifications.pop(key, None)

        if state is None:
            return

        logger.warning(
            "Verification expired chat_id=%s user_id=%s tracked_messages=%s",
            chat_id,
            user_id,
            len(state.message_ids),
        )

        with suppress(TelegramBadRequest, TelegramForbiddenError):
            await bot.delete_message(chat_id, state.verify_message_id)
            logger.info(
                "Expired verification message deleted chat_id=%s user_id=%s verify_message_id=%s",
                chat_id,
                user_id,
                state.verify_message_id,
            )

        for tracked_message_id in state.message_ids:
            with suppress(TelegramBadRequest, TelegramForbiddenError):
                await bot.delete_message(chat_id, tracked_message_id)
                logger.info(
                    "Tracked message deleted after verification timeout chat_id=%s user_id=%s message_id=%s",
                    chat_id,
                    user_id,
                    tracked_message_id,
                )

        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            revoke_messages=True,
        )
        logger.warning(
            "User banned after verification timeout chat_id=%s user_id=%s",
            chat_id,
            user_id,
        )


def _restricted_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False,
    )


async def _allowed_permissions(bot: Bot, chat_id: int) -> ChatPermissions:
    chat = await bot.get_chat(chat_id)

    if chat.permissions is not None:
        return chat.permissions

    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
    )


def _get_lock(key: tuple[int, int]) -> asyncio.Lock:
    lock = verification_locks.get(key)

    if lock is None:
        lock = asyncio.Lock()
        verification_locks[key] = lock

    return lock


def is_verification_pending(chat_id: int, user_id: int) -> bool:
    return (chat_id, user_id) in pending_verifications
