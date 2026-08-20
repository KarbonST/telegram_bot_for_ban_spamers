import logging
from dataclasses import dataclass, field

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from bot.config import config
from bot.database.users.repository import get_user
from bot.logging_utils import chat_repr, text_preview, user_repr
from bot.services.gemini_moderation import classify_message_with_gemini
from bot.services.spam_scoring import score_message_text
from bot.services.verification import (
    cancel_pending_verification,
    ensure_privileged_member_verified,
    reset_verified_status,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SpamModerationResult:
    action: str = "allow"
    score: int = 0
    matched_rules: list[str] = field(default_factory=list)
    gemini_checked: bool = False
    gemini_verdict: str | None = None
    gemini_reason: str | None = None


async def moderate_message_for_spam(message: Message) -> SpamModerationResult:
    text = message.text or message.caption

    if not text or message.from_user is None:
        return SpamModerationResult()

    content_type = _content_type_value(message)
    user = await get_user(message.chat.id, message.from_user.id)
    is_verified = bool(user and user.is_verified)
    score_result = score_message_text(text, content_type)

    logger.info(
        "Spam score evaluated %s %s message_id=%s verified=%s score=%s threshold=%s matched_rules=%s text=%r",
        chat_repr(message.chat),
        user_repr(message.from_user),
        message.message_id,
        is_verified,
        score_result.score,
        config.spam_score_threshold,
        score_result.matched_rules or ["<none>"],
        text_preview(text),
    )

    if score_result.score < config.spam_score_threshold:
        return SpamModerationResult(
            score=score_result.score,
            matched_rules=score_result.matched_rules,
        )

    if await ensure_privileged_member_verified(
        message.bot,
        message.chat.id,
        message.from_user.id,
        source="spam_score",
    ):
        logger.info(
            "Skipping AI spam moderation for privileged member %s %s message_id=%s score=%s",
            chat_repr(message.chat),
            user_repr(message.from_user),
            message.message_id,
            score_result.score,
        )
        return SpamModerationResult(
            action="skip_privileged",
            score=score_result.score,
            matched_rules=score_result.matched_rules,
        )

    gemini_result = await classify_message_with_gemini(
        text=text,
        content_type=content_type,
        is_verified=is_verified,
        local_score=score_result.score,
        matched_rules=score_result.matched_rules,
    )

    if not gemini_result.checked:
        logger.warning(
            "Gemini spam moderation skipped %s %s message_id=%s score=%s matched_rules=%s skipped_reason=%s",
            chat_repr(message.chat),
            user_repr(message.from_user),
            message.message_id,
            score_result.score,
            score_result.matched_rules or ["<none>"],
            gemini_result.skipped_reason,
        )
        return SpamModerationResult(
            score=score_result.score,
            matched_rules=score_result.matched_rules,
        )

    logger.info(
        "Gemini spam moderation completed %s %s message_id=%s score=%s verdict=%s reason=%r",
        chat_repr(message.chat),
        user_repr(message.from_user),
        message.message_id,
        score_result.score,
        gemini_result.verdict,
        gemini_result.reason,
    )

    if gemini_result.verdict != "spam":
        return SpamModerationResult(
            score=score_result.score,
            matched_rules=score_result.matched_rules,
            gemini_checked=True,
            gemini_verdict=gemini_result.verdict,
            gemini_reason=gemini_result.reason,
        )

    await _ban_user_for_spam(
        message=message,
        score=score_result.score,
        matched_rules=score_result.matched_rules,
        reason=gemini_result.reason or "gemini_spam_verdict",
    )

    return SpamModerationResult(
        action="banned",
        score=score_result.score,
        matched_rules=score_result.matched_rules,
        gemini_checked=True,
        gemini_verdict=gemini_result.verdict,
        gemini_reason=gemini_result.reason,
    )


async def _ban_user_for_spam(
    *,
    message: Message,
    score: int,
    matched_rules: list[str],
    reason: str,
) -> None:
    if message.from_user is None:
        return

    await cancel_pending_verification(
        bot=message.bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        reason="spam_detected",
    )
    await reset_verified_status(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        reason="spam_detected",
    )

    try:
        await message.delete()
        logger.warning(
            "Spam message deleted %s %s message_id=%s score=%s matched_rules=%s reason=%r",
            chat_repr(message.chat),
            user_repr(message.from_user),
            message.message_id,
            score,
            matched_rules or ["<none>"],
            reason,
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        logger.warning(
            "Spam message delete skipped %s %s message_id=%s score=%s matched_rules=%s reason=%r",
            chat_repr(message.chat),
            user_repr(message.from_user),
            message.message_id,
            score,
            matched_rules or ["<none>"],
            reason,
        )

    try:
        await message.bot.ban_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            revoke_messages=True,
        )
        logger.warning(
            "User banned by AI spam moderation %s %s message_id=%s score=%s matched_rules=%s reason=%r",
            chat_repr(message.chat),
            user_repr(message.from_user),
            message.message_id,
            score,
            matched_rules or ["<none>"],
            reason,
        )
    except TelegramBadRequest as error:
        if "administrator of the chat" not in str(error).lower():
            raise

        logger.info(
            "AI spam moderation ban skipped because user became admin %s %s message_id=%s score=%s reason=%r",
            chat_repr(message.chat),
            user_repr(message.from_user),
            message.message_id,
            score,
            reason,
        )


def _content_type_value(message: Message) -> str:
    content_type = message.content_type
    return content_type.value if hasattr(content_type, "value") else str(content_type)
