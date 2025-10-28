# app/domain/users/service.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.models import User


# === БАЗОВОЕ: users.user_id == Telegram ID, баланс хранится в users.credits ===

async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    """Вернуть пользователя по Telegram ID, создать с credits=0 если нет."""
    row = await session.execute(select(User).where(User.user_id == telegram_id))
    user = row.scalars().first()
    if user:
        return user

    # создаём минимально, чтобы не зависеть от необязательных колонок
    user = User(user_id=telegram_id, credits=0)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_balance(session: AsyncSession, telegram_id: int) -> int:
    """Баланс в генерациях по Telegram ID (users.credits)."""
    row = await session.execute(select(User.credits).where(User.user_id == telegram_id))
    val = row.scalar_one_or_none()
    return int(val or 0)


async def add_credits(session: AsyncSession, telegram_id: int, qty: int) -> None:
    """Начислить генерации по Telegram ID."""
    await session.execute(
        update(User)
        .where(User.user_id == telegram_id)
        .values(credits=User.credits + int(qty))
    )
    await session.commit()


async def deduct_credits_atomic(session: AsyncSession, telegram_id: int, qty: int) -> bool:
    """
    Атомарно списать генерации (credits >= qty).
    Возвращает True, если списали.
    """
    res = await session.execute(
        update(User)
        .where(User.user_id == telegram_id, User.credits >= qty)
        .values(credits=User.credits - int(qty))
        .execution_options(synchronize_session=False)
    )
    if res.rowcount == 0:
        await session.rollback()
        return False
    await session.commit()
    return True


# === ЛОКАЛЬ/апсерт по /start (колонка users.locale есть в вашей БД) ===

# async def set_locale(session: AsyncSession, telegram_id: int, locale: str) -> None:
#     await session.execute(
#         update(User).where(User.user_id == telegram_id).values(locale=locale)
#     )
#     await session.commit()


# async def get_locale(session: AsyncSession, telegram_id: int) -> str | None:
#     row = await session.execute(select(User.locale).where(User.user_id == telegram_id))
#     return row.scalar_one_or_none()

async def set_locale(session, user_id: int, locale: str) -> None:
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(locale=locale)
        .execution_options(synchronize_session=False)
    )
    await session.commit()

async def get_locale(session, user_id: int):
    row = await session.execute(
        select(User.locale).where(User.user_id == user_id)
    )
    return row.scalar_one_or_none()



async def upsert_from_message(session: AsyncSession, msg) -> User:
    """
    Создать пользователя по сообщению, если его ещё нет.
    Схема: users.user_id (TG ID), users.credits.
    """
    tgid = msg.from_user.id
    row = await session.execute(select(User).where(User.user_id == tgid))
    user = row.scalars().first()

    if user:
        # при желании можно обновлять username, если колонка есть:
        try:
            if hasattr(User, "username"):
                new_username = msg.from_user.username or None
                if new_username and new_username != (getattr(user, "username", None)):
                    await session.execute(
                        update(User).where(User.user_id == tgid).values(username=new_username)
                    )
                    await session.commit()
        except Exception:
            pass
        return user

    user = User(user_id=tgid, credits=0)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
