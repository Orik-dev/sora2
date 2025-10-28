from __future__ import annotations

import contextlib
from aiogram import Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from arq.connections import create_pool, RedisSettings

from app.core.db import SessionLocal
from app.core.settings import settings
from app.bot.keyboards.common import kb_vertical_toggle
from app.utils.msg import edit_or_send
from app.utils.tg import safe_cb_answer
from app.domain.users.service import get_or_create_user

router = Router(name="text")

def register_text_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)

async def _session() -> AsyncSession:
    return SessionLocal()

class T2V(StatesGroup):
    waiting_prompt = State()

@router.callback_query(F.data == "menu:text")
async def menu_text(cb: CallbackQuery, state: FSMContext):
    async with SessionLocal() as session:
        await state.clear()
        user = await get_or_create_user(session, cb.from_user.id)

        needed = int(getattr(settings, "GENERATION_COST", 1) or 1)
        if user.credits < needed:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Купить генерации", callback_data="menu:packages")]
            ])
            await edit_or_send(cb, "❌ У вас недостаточно генераций(", reply_markup=kb)
            await safe_cb_answer(cb)
            return

        await state.update_data(ar="9:16", model="sora2-t2v")
        await edit_or_send(cb, "✏️ Введите описание того, что должно происходить в видео:", reply_markup=kb_vertical_toggle(is_vertical=True))
        await state.set_state(T2V.waiting_prompt)
        await safe_cb_answer(cb)

@router.callback_query(T2V.waiting_prompt, F.data == "toggle:ar")
async def toggle_ar(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ar = data.get("ar", "9:16")
    new_ar = "16:9" if ar == "9:16" else "9:16"
    await state.update_data(ar=new_ar)
    await edit_or_send(cb, "✏️ Введите описание того, что должно происходить в видео:", reply_markup=kb_vertical_toggle(is_vertical=(new_ar=="9:16")))
    await safe_cb_answer(cb)

@router.message(T2V.waiting_prompt, F.photo)
async def photo_in_text_mode(msg: Message, state: FSMContext):
    await msg.answer("❌ Генерация по фото не доступна в режиме текста, пришлите только описание.")

@router.message(T2V.waiting_prompt, F.text, ~F.text.regexp(r"^/"))
async def set_prompt(msg: Message, state: FSMContext):
    txt = (msg.text or "").strip()
    if len(txt) > 2000:
        await msg.answer("❌ Описание слишком длинное. Максимум 2000 символов."); return
    if len(txt) < 5:
        await msg.answer("❌ Описание слишком короткое. Минимум 5 символов."); return

    data = await state.get_data()
    ar = data.get("ar", "9:16")

    processing = await msg.answer("🔄 Отправляем запрос на генерацию…")
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await redis.enqueue_job(
            "queue_generation",
            telegram_id=msg.from_user.id,
            prompt=txt,
            model="sora2-t2v",
            aspect_ratio=ar,
            images_list=None,
        )
    except Exception:
        with contextlib.suppress(Exception): await processing.delete()
        await msg.answer("❌ Ошибка генерации видео: попробуйте переделать промт")
        return

    with contextlib.suppress(Exception): await processing.delete()
    await state.clear()
    await msg.answer(
        "🎬 Видео начало создаваться. Это может занять до 10 минут.\n"
        "Я пришлю видео сюда, когда оно будет готово!"
    )
