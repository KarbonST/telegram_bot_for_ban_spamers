from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)

from bot.database.base import Base
from bot.database.users.users import User


engine = create_async_engine(
    "sqlite+aiosqlite:///bot.db",
    echo=True,
)


async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
