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
    join_verification_enabled: bool
    first_message_verification_enabled: bool
    gigachat_spam_moderation_enabled: bool
    gigachat_auth_key: str | None
    gigachat_model: str
    gigachat_scope: str
    spam_score_threshold: int
    gigachat_request_timeout_seconds: int
    gigachat_verify_ssl: bool

    @property
    def message_moderation_mode(self) -> str:
        if (
            self.first_message_verification_enabled
            and self.gigachat_spam_moderation_enabled
        ):
            return "double_verification"

        if self.first_message_verification_enabled:
            return "verification_only"

        if self.gigachat_spam_moderation_enabled:
            return "gigachat_only"

        return "messages_checks_disabled"


config = Config(
    telegram_token=os.getenv("TG_BOT_TOKEN"),
    allowed_chat_id=_to_int(os.getenv("ALLOWED_CHAT_ID")),
    verification_timeout_seconds=_to_int(
        os.getenv("VERIFICATION_TIMEOUT_SECONDS"),
        default=30,
    ),
    join_verification_enabled=_to_bool(
        os.getenv("JOIN_VERIFICATION_ENABLED"),
        default=True,
    ),
    first_message_verification_enabled=_to_bool(
        os.getenv("FIRST_MESSAGE_VERIFICATION_ENABLED"),
        default=True,
    ),
    gigachat_spam_moderation_enabled=_to_bool(
        os.getenv("GIGACHAT_SPAM_MODERATION_ENABLED"),
        default=False,
    ),
    gigachat_auth_key=os.getenv("GIGACHAT_AUTH_KEY") or None,
    gigachat_model=os.getenv("GIGACHAT_MODEL") or "GigaChat-2",
    gigachat_scope=os.getenv("GIGACHAT_SCOPE") or "GIGACHAT_API_PERS",
    spam_score_threshold=_to_int(
        os.getenv("SPAM_SCORE_THRESHOLD"),
        default=4,
    ),
    gigachat_request_timeout_seconds=_to_int(
        os.getenv("GIGACHAT_REQUEST_TIMEOUT_SECONDS"),
        default=20,
    ),
    gigachat_verify_ssl=_to_bool(
        os.getenv("GIGACHAT_VERIFY_SSL"),
        default=True,
    ),
)
