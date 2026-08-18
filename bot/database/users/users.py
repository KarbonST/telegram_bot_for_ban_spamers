from sqlalchemy import BigInteger, Boolean, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped
from bot.database.base import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("chat_id", "telegram_id", name="uq_users_chat_telegram"),
    )

    id: Mapped[int] = mapped_column (
        primary_key=True
    )
    chat_id: Mapped[int] = mapped_column (
        BigInteger
    )
    telegram_id: Mapped[int] = mapped_column(
        BigInteger
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
