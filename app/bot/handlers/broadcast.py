# from __future__ import annotations
# import uuid
# from aiogram import Router, Dispatcher
# from aiogram.filters import Command
# from aiogram.types import Message
# from sqlalchemy import select, update
# from arq.connections import ArqRedis, RedisSettings, create_pool

# from app.core.settings import settings
# from app.core.db import SessionLocal
# from app.models.models import BroadcastJob, User

# router = Router(name=__name__)

# def register_broadcast_handlers(dp: Dispatcher) -> None:
#     dp.include_router(router)

# def _is_admin(uid: int) -> bool:
#     return settings.ADMIN_ID and int(settings.ADMIN_ID) == int(uid)

# async def _arq() -> ArqRedis:
#     return await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))

# @router.message(Command("broadcast"))
# async def cmd_broadcast(msg: Message):
#     if not _is_admin(msg.from_user.id):
#         return
#     text = (msg.text or "").split(" ", 1)
#     if len(text) < 2 or not text[1].strip():
#         await msg.answer("Использование: <code>/broadcast Текст рассылки</code>")
#         return
#     payload = text[1].strip()

#     # создаём Job
#     job_id = str(uuid.uuid4())
#     async with SessionLocal() as session:
#         total = (await session.execute(select(User.user_id))).scalars().unique().all()
#         bj = BroadcastJob(
#             id=job_id,
#             created_by=msg.from_user.id,
#             text=payload,
#             status="queued",
#             total=len(total)
#         )
#         session.add(bj)
#         await session.commit()

#     # кидаем в ARQ
#     arq = await _arq()
#     await arq.enqueue_job("broadcast_send", job_id)

#     await msg.answer(f"🚀 Запустил рассылку #{job_id}\nВсего пользователей: {bj.total}\nКоманда отмены: /broadcast_cancel {job_id}\nСтатус: /broadcast_status {job_id}")

# @router.message(Command("broadcast_cancel"))
# async def cmd_broadcast_cancel(msg: Message):
#     if not _is_admin(msg.from_user.id):
#         return
#     parts = (msg.text or "").split(" ", 1)
#     if len(parts) < 2:
#         await msg.answer("Использование: <code>/broadcast_cancel JOB_ID</code>")
#         return
#     job_id = parts[1].strip()
#     async with SessionLocal() as session:
#         await session.execute(
#             update(BroadcastJob)
#             .where(BroadcastJob.id == job_id)
#             .values(status="cancelled")
#         )
#         await session.commit()
#     await msg.answer(f"⏹ Отменил рассылку #{job_id}")

# @router.message(Command("broadcast_status"))
# async def cmd_broadcast_status(msg: Message):
#     if not _is_admin(msg.from_user.id):
#         return
#     parts = (msg.text or "").split(" ", 1)
#     if len(parts) < 2:
#         await msg.answer("Использование: <code>/broadcast_status JOB_ID</code>")
#         return
#     job_id = parts[1].strip()
#     async with SessionLocal() as session:
#         row = await session.execute(select(BroadcastJob).where(BroadcastJob.id == job_id))
#         bj = row.scalars().first()
#     if not bj:
#         await msg.answer("Не нашёл такую рассылку")
#         return
#     await msg.answer(f"Рассылка #{bj.id}\nСтатус: {bj.status}\nВсего: {bj.total}\nОтправлено: {bj.sent}\nОшибок: {bj.failed}\n{('Заметка: ' + bj.note) if bj.note else ''}")



from __future__ import annotations
import uuid
from aiogram import Router, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update
from arq.connections import create_pool, RedisSettings

from app.core.settings import settings
from app.core.db import SessionLocal
from app.models.models import BroadcastJob, User

router = Router(name=__name__)


class BroadcastStates(StatesGroup):
    waiting_for_message = State()


def register_broadcast_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)


def _is_admin(uid: int) -> bool:
    return settings.ADMIN_ID and int(settings.ADMIN_ID) == int(uid)


@router.message(Command("broadcast"))
async def cmd_broadcast(msg: Message, state: FSMContext):
    """Начать рассылку: админ вводит /broadcast и отправляет следующее сообщение"""
    if not _is_admin(msg.from_user.id):
        return
    
    await state.set_state(BroadcastStates.waiting_for_message)
    await msg.answer(
        "📣 <b>Отправьте сообщение для рассылки:</b>\n\n"
        "✅ Поддерживается:\n"
        "• Текст\n"
        "• Фото + подпись\n"
        "• Видео + подпись\n\n"
        "💡 <b>HTML-форматирование:</b>\n"
        "• <code>&lt;b&gt;жирный&lt;/b&gt;</code> → <b>жирный</b>\n"
        "• <code>&lt;i&gt;курсив&lt;/i&gt;</code> → <i>курсив</i>\n"
        "• <code>&lt;code&gt;код&lt;/code&gt;</code> → <code>код</code>\n"
        "• <code>&lt;a href=\"url\"&gt;ссылка&lt;/a&gt;</code>\n\n"
        "Отправьте сообщение, и оно будет разослано всем пользователям.",
        parse_mode="HTML"
    )


@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(msg: Message, state: FSMContext):
    """Обработка сообщения для рассылки"""
    if not _is_admin(msg.from_user.id):
        await state.clear()
        return

    # Извлекаем текст
    text = (msg.caption or msg.text or "").strip()
    if not text:
        await msg.answer("❌ Сообщение должно содержать текст или подпись!")
        return

    # Определяем тип медиа
    media_type = None
    media_file_id = None

    if msg.photo:
        media_type = "photo"
        media_file_id = msg.photo[-1].file_id  # ✅ Используем file_id
    elif msg.video:
        media_type = "video"
        media_file_id = msg.video.file_id  # ✅ Используем file_id

    # Создаем задачу рассылки
    job_id = str(uuid.uuid4())
    
    async with SessionLocal() as session:
        # Получаем всех пользователей
        result = await session.execute(select(User.user_id))
        total_users = result.scalars().unique().all()
        
        bj = BroadcastJob(
            id=job_id,
            created_by=msg.from_user.id,
            text=text,  # ✅ Сохраняем текст с HTML-тегами как есть
            media_type=media_type,
            media_file_id=media_file_id,  # ✅ Сохраняем file_id (не скачиваем!)
            media_file_path=None,  # Не используется
            status="queued",
            total=len(total_users)
        )
        session.add(bj)
        await session.commit()

    # Запускаем задачу в ARQ
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await redis_pool.enqueue_job("broadcast_send", job_id)

    # Формируем ответ
    media_info = ""
    if media_type == "photo":
        media_info = "\n📸 С фото"
    elif media_type == "video":
        media_info = "\n🎬 С видео"
    
    await msg.answer(
        f"🚀 Запустил рассылку <code>#{job_id}</code>{media_info}\n"
        f"Всего пользователей: <b>{len(total_users)}</b>\n\n"
        f"📊 Статус: <code>/broadcast_status {job_id}</code>\n"
        f"⏹ Отмена: <code>/broadcast_cancel {job_id}</code>",
        parse_mode="HTML"
    )
    
    await state.clear()


@router.message(Command("broadcast_cancel"))
async def cmd_broadcast_cancel(msg: Message):
    """Отменить рассылку"""
    if not _is_admin(msg.from_user.id):
        return
    
    parts = (msg.text or "").split(" ", 1)
    if len(parts) < 2:
        await msg.answer(
            "Использование: <code>/broadcast_cancel JOB_ID</code>",
            parse_mode="HTML"
        )
        return
    
    job_id = parts[1].strip()
    
    async with SessionLocal() as session:
        await session.execute(
            update(BroadcastJob)
            .where(BroadcastJob.id == job_id)
            .values(status="cancelled")
        )
        await session.commit()
    
    await msg.answer(
        f"⏹ Отменил рассылку <code>#{job_id}</code>",
        parse_mode="HTML"
    )


@router.message(Command("broadcast_status"))
async def cmd_broadcast_status(msg: Message):
    """Статус рассылки"""
    if not _is_admin(msg.from_user.id):
        return
    
    parts = (msg.text or "").split(" ", 1)
    if len(parts) < 2:
        await msg.answer(
            "Использование: <code>/broadcast_status JOB_ID</code>",
            parse_mode="HTML"
        )
        return
    
    job_id = parts[1].strip()
    
    async with SessionLocal() as session:
        row = await session.execute(
            select(BroadcastJob).where(BroadcastJob.id == job_id)
        )
        bj = row.scalars().first()
    
    if not bj:
        await msg.answer("❌ Рассылка не найдена")
        return
    
    # Формируем информацию о медиа
    media_info = ""
    if bj.media_type == "photo":
        media_info = "\n📸 Тип: фото"
    elif bj.media_type == "video":
        media_info = "\n🎬 Тип: видео"
    
    # Вычисляем процент выполнения
    progress = ""
    if bj.total > 0:
        done = bj.sent + bj.failed + bj.fallback
        percent = (done / bj.total) * 100
        progress = f"\n📈 Прогресс: {done}/{bj.total} ({percent:.1f}%)"
    
    await msg.answer(
        f"📊 Рассылка <code>#{bj.id}</code>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Статус: <b>{bj.status}</b>{media_info}{progress}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Всего: <b>{bj.total}</b>\n"
        f"✅ Отправлено (медиа): <b>{bj.sent}</b>\n"
        f"⚠️ Fallback (текст): <b>{bj.fallback}</b>\n"
        f"❌ Ошибок: <b>{bj.failed}</b>\n"
        f"{('💬 ' + bj.note) if bj.note else ''}",
        parse_mode="HTML"
    )


@router.message(Command("broadcast_test"))
async def cmd_broadcast_test(msg: Message, state: FSMContext):
    """Тестовая рассылка только админу"""
    if not _is_admin(msg.from_user.id):
        return
    
    await state.clear()
    
    # Извлекаем текст
    text = (msg.caption or msg.text or "").strip()
    if not text.startswith("/broadcast_test"):
        return
    
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer(
            "Использование:\n"
            "• Текст: <code>/broadcast_test Ваш текст</code>\n"
            "• Фото: прикрепите фото + <code>/broadcast_test Текст</code>\n"
            "• Видео: прикрепите видео + <code>/broadcast_test Текст</code>\n\n"
            "💡 Поддерживается HTML: <code>&lt;b&gt;жирный&lt;/b&gt;</code>",
            parse_mode="HTML"
        )
        return
    
    payload = parts[1].strip()
    
    # Определяем медиа
    media_type = None
    media_file_id = None
    
    if msg.photo:
        media_type = "photo"
        media_file_id = msg.photo[-1].file_id
    elif msg.video:
        media_type = "video"
        media_file_id = msg.video.file_id
    
    # Отправляем тестовое сообщение
    try:
        if media_type == "photo" and media_file_id:
            await msg.bot.send_photo(
                msg.from_user.id,
                photo=media_file_id,
                caption=f"🧪 ТЕСТ:\n\n{payload}",
                parse_mode="HTML"  # ✅ HTML форматирование
            )
        elif media_type == "video" and media_file_id:
            await msg.bot.send_video(
                msg.from_user.id,
                video=media_file_id,
                caption=f"🧪 ТЕСТ:\n\n{payload}",
                parse_mode="HTML"  # ✅ HTML форматирование
            )
        else:
            await msg.answer(
                f"🧪 ТЕСТ:\n\n{payload}",
                parse_mode="HTML"  # ✅ HTML форматирование
            )
        
        await msg.answer("✅ Тест отправлен!", parse_mode="HTML")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}", parse_mode="HTML")