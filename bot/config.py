from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class Config:
    telegram_token: str


config = Config(
    telegram_token=os.getenv("TG_BOT_TOKEN"),
)
