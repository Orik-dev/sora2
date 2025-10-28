from __future__ import annotations
import uuid
from aiogram import Router, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, update
from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.settings import settings
from app.core.db import SessionLocal
from app.models.models import BroadcastJob, User

router = Router(name=__name__)

def register_broadcast_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)

def _is_admin(uid: int) -> bool:
    return settings.ADMIN_ID and int(settings.ADMIN_ID) == int(uid)

async def _arq() -> ArqRedis:
    return await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))

@router.message(Command("broadcast"))
async def cmd_broadcast(msg: Message):
    if not _is_admin(msg.from_user.id):
        return
    text = (msg.text or "").split(" ", 1)
    if len(text) < 2 or not text[1].strip():
        await msg.answer("Использование: <code>/broadcast Текст рассылки</code>")
        return
    payload = text[1].strip()

    # создаём Job
    job_id = str(uuid.uuid4())
    async with SessionLocal() as session:
        total = (await session.execute(select(User.user_id))).scalars().unique().all()
        bj = BroadcastJob(
            id=job_id,
            created_by=msg.from_user.id,
            text=payload,
            status="queued",
            total=len(total)
        )
        session.add(bj)
        await session.commit()

    # кидаем в ARQ
    arq = await _arq()
    await arq.enqueue_job("broadcast_send", job_id)

    await msg.answer(f"🚀 Запустил рассылку #{job_id}\nВсего пользователей: {bj.total}\nКоманда отмены: /broadcast_cancel {job_id}\nСтатус: /broadcast_status {job_id}")

@router.message(Command("broadcast_cancel"))
async def cmd_broadcast_cancel(msg: Message):
    if not _is_admin(msg.from_user.id):
        return
    parts = (msg.text or "").split(" ", 1)
    if len(parts) < 2:
        await msg.answer("Использование: <code>/broadcast_cancel JOB_ID</code>")
        return
    job_id = parts[1].strip()
    async with SessionLocal() as session:
        await session.execute(
            update(BroadcastJob)
            .where(BroadcastJob.id == job_id)
            .values(status="cancelled")
        )
        await session.commit()
    await msg.answer(f"⏹ Отменил рассылку #{job_id}")

@router.message(Command("broadcast_status"))
async def cmd_broadcast_status(msg: Message):
    if not _is_admin(msg.from_user.id):
        return
    parts = (msg.text or "").split(" ", 1)
    if len(parts) < 2:
        await msg.answer("Использование: <code>/broadcast_status JOB_ID</code>")
        return
    job_id = parts[1].strip()
    async with SessionLocal() as session:
        row = await session.execute(select(BroadcastJob).where(BroadcastJob.id == job_id))
        bj = row.scalars().first()
    if not bj:
        await msg.answer("Не нашёл такую рассылку")
        return
    await msg.answer(f"Рассылка #{bj.id}\nСтатус: {bj.status}\nВсего: {bj.total}\nОтправлено: {bj.sent}\nОшибок: {bj.failed}\n{('Заметка: ' + bj.note) if bj.note else ''}")
