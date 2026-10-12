import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.database.users.repository import get_user
from bot.logging_utils import chat_repr, text_preview, user_repr
from bot.services.verification import is_verification_pending


logger = logging.getLogger(__name__)


class MessageAuditMiddleware(BaseMiddleware):
    def __init__(self, *, update_type: str) -> None:
        self.update_type = update_type

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if event.chat.type in {"group", "supergroup"}:
            verified_status = "n/a"
            pending_status = "n/a"

            if (
                event.sender_chat is None
                and event.from_user is not None
                and not event.from_user.is_bot
            ):
                try:
                    user = await get_user(event.chat.id, event.from_user.id)
                    verified_status = "yes" if user and user.is_verified else "no"
                    pending_status = (
                        "yes"
                        if is_verification_pending(event.chat.id, event.from_user.id)
                        else "no"
                    )
                except Exception:
                    logger.exception(
                        "Failed to read verification state for message audit "
                        "chat_id=%s user_id=%s message_id=%s",
                        event.chat.id,
                        event.from_user.id,
                        event.message_id,
                    )
                    verified_status = "lookup_failed"
                    pending_status = "lookup_failed"

            logger.info(
                "Message audit update_type=%s chat=%s message_id=%s date=%s "
                "edit_date=%s content_type=%s "
                "from_user=%s sender_chat=%s verified=%s pending_verification=%s "
                "automatic_forward=%s new_chat_members=%s text=%r",
                self.update_type,
                chat_repr(event.chat),
                event.message_id,
                event.date.isoformat(),
                event.edit_date.isoformat() if event.edit_date else None,
                event.content_type,
                user_repr(event.from_user) if event.from_user else "<no-user>",
                chat_repr(event.sender_chat) if event.sender_chat else "<no-sender-chat>",
                verified_status,
                pending_status,
                event.is_automatic_forward,
                _new_members_repr(event),
                text_preview(event.text or event.caption),
            )

        return await handler(event, data)


def _new_members_repr(message: Message) -> str:
    if not message.new_chat_members:
        return "<none>"

    return "[" + ", ".join(user_repr(member) for member in message.new_chat_members) + "]"
