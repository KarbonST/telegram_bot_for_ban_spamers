from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None

    return int(value)


@dataclass
class Config:
    telegram_token: str
    allowed_chat_id: int | None


config = Config(
    telegram_token=os.getenv("TG_BOT_TOKEN"),
    allowed_chat_id=_to_int(os.getenv("ALLOWED_CHAT_ID")),
)
