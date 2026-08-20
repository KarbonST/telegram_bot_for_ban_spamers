from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


def _to_int(value: str | None, default: int | None = None) -> int | None:
    if value is None:
        return default

    return int(value)


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    telegram_token: str
    allowed_chat_id: int | None
    verification_timeout_seconds: int
    first_message_verification_enabled: bool
    gemini_spam_moderation_enabled: bool
    gemini_api_key: str | None
    gemini_model: str
    spam_score_threshold: int
    gemini_daily_request_limit: int
    gemini_request_timeout_seconds: int

    @property
    def message_moderation_mode(self) -> str:
        if (
            self.first_message_verification_enabled
            and self.gemini_spam_moderation_enabled
        ):
            return "double_verification"

        if self.first_message_verification_enabled:
            return "verification_only"

        if self.gemini_spam_moderation_enabled:
            return "gemini_only"

        return "messages_checks_disabled"


config = Config(
    telegram_token=os.getenv("TG_BOT_TOKEN"),
    allowed_chat_id=_to_int(os.getenv("ALLOWED_CHAT_ID")),
    verification_timeout_seconds=_to_int(
        os.getenv("VERIFICATION_TIMEOUT_SECONDS"),
        default=30,
    ),
    first_message_verification_enabled=_to_bool(
        os.getenv("FIRST_MESSAGE_VERIFICATION_ENABLED"),
        default=True,
    ),
    gemini_spam_moderation_enabled=_to_bool(
        os.getenv("GEMINI_SPAM_MODERATION_ENABLED"),
        default=False,
    ),
    gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
    gemini_model=os.getenv("GEMINI_MODEL") or "gemini-2.5-flash-lite",
    spam_score_threshold=_to_int(
        os.getenv("SPAM_SCORE_THRESHOLD"),
        default=4,
    ),
    gemini_daily_request_limit=_to_int(
        os.getenv("GEMINI_DAILY_REQUEST_LIMIT"),
        default=20,
    ),
    gemini_request_timeout_seconds=_to_int(
        os.getenv("GEMINI_REQUEST_TIMEOUT_SECONDS"),
        default=15,
    ),
)
