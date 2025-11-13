from __future__ import annotations

import contextlib
from aiogram import Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from arq.connections import RedisSettings, create_pool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.logger import logger
from app.core.settings import settings
from app.bot.i18n import _load_locales, get_user_lang
from app.utils.msg import edit_or_send
from app.utils.tg import safe_cb_answer
from app.domain.users.service import get_or_create_user

router = Router(name="image")

def register_image_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)

async def _session() -> AsyncSession:
    return SessionLocal()

class I2V(StatesGroup):
    waiting_photo = State()    # ждём фото
    waiting_caption = State()  # если фото пришло без подписи — ждём подпись

async def _strings(session: AsyncSession, user_id: int) -> dict[str, str]:
    lang = await get_user_lang(session, user_id)
    return _load_locales()[lang]

@router.callback_query(F.data == "menu:image")
async def menu_image(cb: CallbackQuery, state: FSMContext):
    async with SessionLocal() as session:
        await state.clear()
        user = await get_or_create_user(session, cb.from_user.id)

        # ранняя проверка баланса
        needed = settings.GENERATION_COST
        if user.credits < needed:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Купить генерации", callback_data="menu:packages")],
                [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/guard_gpt")]
            ])
            await edit_or_send(
                cb, 
                "❌ <b>Недостаточно генераций</b>\n\n"
                "Пополните баланс или напишите в поддержку:\n"
                "👉 @guard_gpt", 
                reply_markup=kb
            )
            await safe_cb_answer(cb)
            return

        # ✅ БЕЗ aspect_ratio - видео будет в формате загруженного фото
        await state.update_data(model="sora2-i2v")

        await edit_or_send(
            cb,
            "📸 <b>Отправьте изображение</b>\n",
            # "💡 Видео будет создано в том же формате, что и ваше фото\n"
            # "(квадратное фото → квадратное видео, вертикальное → вертикальное)",
            reply_markup=None  # ✅ Убрали кнопку переключения
        )
        await state.set_state(I2V.waiting_photo)
        await safe_cb_answer(cb)

# ✅ УБРАЛИ callback для toggle:ar - он больше не нужен

@router.message(I2V.waiting_photo, F.photo)
async def got_photo_with_optional_caption(msg: Message, state: FSMContext):
    ph = msg.photo[-1]
    f = await msg.bot.get_file(ph.file_id)
    file_url = f"https://api.telegram.org/file/bot{msg.bot.token}/{f.file_path}"

    caption = (msg.caption or "").strip()
    if caption:
        if len(caption) > 2000:
            await msg.answer("❌ Описание слишком длинное. Максимум 2000 символов.")
            return
        if len(caption) < 5:
            await msg.answer("❌ Описание слишком короткое. Минимум 5 символов.")
            return

        processing = await msg.answer("🔄 Отправляем запрос на генерацию…")
        try:
            redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            await redis.enqueue_job(
                "queue_generation",
                telegram_id=msg.from_user.id,
                prompt=caption,
                model="sora2-i2v",
                aspect_ratio=None,  # ✅ Не передаём AR - API сам определит из фото
                images_list=[file_url],
            )
        except Exception:
            with contextlib.suppress(Exception): await processing.delete()
            logger.exception("I2V enqueue failed")
            await msg.answer(
                "❌ <b>Ошибка генерации видео</b>\n\n"
                "Попробуйте переформулировать промпт или напишите в поддержку:\n"
                "👉 @guard_gpt",
                parse_mode="HTML"
            )
            return

        with contextlib.suppress(Exception): await processing.delete()
        await state.clear()
        await msg.answer(
            "🎬 Видео начало создаваться. Это может занять до 10 минут.\n"
            "Я пришлю видео сюда, когда оно будет готово!"
        )
        return

    # фото без подписи → сохраняем URL и просим текст
    await state.update_data(photo_url=file_url)
    await state.set_state(I2V.waiting_caption)
    await msg.answer("✏️ Введите текст-промпт (что должно происходить на фото)")

@router.message(I2V.waiting_photo, F.text, ~F.text.regexp(r"^/"))
async def reject_text_in_photo_mode(msg: Message, state: FSMContext):
    await msg.answer("❌ Пожалуйста, отправьте изображение для генерации видео.")

@router.message(I2V.waiting_caption, F.text, ~F.text.regexp(r"^/"))
async def got_caption_after_photo(msg: Message, state: FSMContext):
    prompt = (msg.text or "").strip()
    if len(prompt) > 2000:
        await msg.answer("❌ Описание слишком длинное. Максимум 2000 символов."); return
    if len(prompt) < 5:
        await msg.answer("❌ Описание слишком короткое. Минимум 5 символов."); return

    data = await state.get_data()
    file_url = data.get("photo_url")
    if not file_url:
        await state.clear()
        await msg.answer("📸 Отправьте изображение.")
        return

    processing = await msg.answer("🔄 Отправляем запрос на генерацию…")
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await redis.enqueue_job(
            "queue_generation",
            telegram_id=msg.from_user.id,
            prompt=prompt,
            model="sora2-i2v",
            aspect_ratio=None,  # ✅ Не передаём AR - API сам определит из фото
            images_list=[file_url],
        )
    except Exception:
        with contextlib.suppress(Exception): await processing.delete()
        logger.exception("I2V enqueue failed")
        await msg.answer(
            "❌ <b>Ошибка генерации видео</b>\n\n"
            "Попробуйте переформулировать промпт или напишите в поддержку:\n"
            "👉 @guard_gpt",
            parse_mode="HTML"
        )
        return

    with contextlib.suppress(Exception): await processing.delete()
    await state.clear()
    await msg.answer(
        "🎬 Видео начало создаваться. Это займёт несколько минут.\n"
        "Я пришлю видео сюда, когда оно будет готово!"
    )

@router.message(F.text.regexp(r"^/cancel$"))
async def cancel_any(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✅ Ок, отменил. Можно начать заново.")