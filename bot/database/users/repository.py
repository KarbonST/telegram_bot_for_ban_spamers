from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot.database.session import async_session
from bot.database.users.users import User

async def get_user(
        chat_id: int,
        telegram_id: int
) -> User | None:

    async with async_session() as session:

        result = await session.execute(
            select(User)
            .where(User.chat_id == chat_id,
                   User.telegram_id == telegram_id)
        )

        return result.scalar_one_or_none()

async def create_user(
        chat_id: int,
        telegram_id: int,
) -> User | None:

    async with async_session() as session:

        user = User(
            chat_id=chat_id,
            telegram_id=telegram_id,
        )

        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            result = await session.execute(
                select(User)
                .where(User.chat_id == chat_id,
                       User.telegram_id == telegram_id)
            )
            return result.scalar_one()

        await session.refresh(user)
        return user


async def get_or_create_user(
        chat_id: int,
        telegram_id: int,
) -> User:
    user = await get_user(chat_id, telegram_id)

    if user is not None:
        return user

    return await create_user(chat_id, telegram_id)


async def mark_user_verified(
        chat_id: int,
        telegram_id: int,
) -> User:
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .where(User.chat_id == chat_id,
                   User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                chat_id=chat_id,
                telegram_id=telegram_id,
                is_verified=True,
            )
            session.add(user)
        else:
            user.is_verified = True

        await session.commit()
        await session.refresh(user)

        return user


async def mark_user_unverified(
        chat_id: int,
        telegram_id: int,
) -> User | None:
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .where(User.chat_id == chat_id,
                   User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            return None

        user.is_verified = False
        await session.commit()
        await session.refresh(user)

        return user
