from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


def _to_int(value: str | None, default: int | None = None) -> int | None:
    if value is None:
        return default

    return int(value)


@dataclass
class Config:
    telegram_token: str
    allowed_chat_id: int | None
    verification_timeout_seconds: int


config = Config(
    telegram_token=os.getenv("TG_BOT_TOKEN"),
    allowed_chat_id=_to_int(os.getenv("ALLOWED_CHAT_ID")),
    verification_timeout_seconds=_to_int(
        os.getenv("VERIFICATION_TIMEOUT_SECONDS"),
        default=30,
    ),
)
