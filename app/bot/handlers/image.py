# from __future__ import annotations

# import contextlib
# from aiogram import Router, F, Dispatcher
# from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.fsm.context import FSMContext
# from arq.connections import RedisSettings, create_pool
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.db import SessionLocal
# from app.core.logger import logger
# from app.core.settings import settings
# from app.bot.i18n import _load_locales, get_user_lang
# from app.bot.keyboards.common import kb_vertical_toggle
# from app.utils.msg import edit_or_send
# from app.utils.tg import safe_cb_answer
# from app.domain.users.service import get_or_create_user

# router = Router(name="image")

# def register_image_handlers(dp: Dispatcher) -> None:
#     dp.include_router(router)

# async def _session() -> AsyncSession:
#     return SessionLocal()

# class I2V(StatesGroup):
#     waiting_photo = State()    # ждём фото (+ подпись)
#     waiting_caption = State()  # если фото пришло без подписи — ждём подпись

# async def _strings(session: AsyncSession, user_id: int) -> dict[str, str]:
#     lang = await get_user_lang(session, user_id)
#     return _load_locales()[lang]

# @router.callback_query(F.data == "menu:image")
# async def menu_image(cb: CallbackQuery, state: FSMContext):
#     async with SessionLocal() as session:
#         await state.clear()
#         user = await get_or_create_user(session, cb.from_user.id)

#         # ранняя проверка баланса
#         needed = settings.GENERATION_COST
#         if user.credits < needed:
#             kb = InlineKeyboardMarkup(inline_keyboard=[
#                 [InlineKeyboardButton(text="💳 Купить генерации", callback_data="menu:packages")]
#             ])
#             await edit_or_send(cb, "❌ У вас недостаточно генераций(", reply_markup=kb)
#             await safe_cb_answer(cb)
#             return

#         # дефолт: вертикально 9:16
#         await state.update_data(ar="9:16", model="sora2-i2v")

#         await edit_or_send(
#             cb,
#             "📸 Отправьте изображение вместе с описанием (промтом).",
#             reply_markup=kb_vertical_toggle(is_vertical=True),
#         )
#         await state.set_state(I2V.waiting_photo)
#         await safe_cb_answer(cb)

# @router.callback_query(I2V.waiting_photo, F.data == "toggle:ar")
# async def toggle_ar(cb: CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     ar = data.get("ar", "9:16")
#     new_ar = "16:9" if ar == "9:16" else "9:16"
#     await state.update_data(ar=new_ar)
#     is_vertical = (new_ar == "9:16")
#     await edit_or_send(
#         cb,
#         "📸 Отправьте изображение вместе с описанием (промтом) в одном сообщении (в подписи).",
#         reply_markup=kb_vertical_toggle(is_vertical=is_vertical),
#     )
#     await safe_cb_answer(cb)

# @router.message(I2V.waiting_photo, F.photo)
# async def got_photo_with_optional_caption(msg: Message, state: FSMContext):
#     ph = msg.photo[-1]
#     f = await msg.bot.get_file(ph.file_id)
#     file_url = f"https://api.telegram.org/file/bot{msg.bot.token}/{f.file_path}"

#     caption = (msg.caption or "").strip()
#     if caption:
#         if len(caption) > 2000:
#             await msg.answer("❌ Описание слишком длинное. Максимум 2000 символов.")
#             return
#         if len(caption) < 5:
#             await msg.answer("❌ Описание слишком короткое. Минимум 5 символов.")
#             return

#         data = await state.get_data()
#         ar = data.get("ar", "9:16")

#         processing = await msg.answer("🔄 Отправляем запрос на генерацию…")
#         try:
#             redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
#             await redis.enqueue_job(
#                 "queue_generation",
#                 telegram_id=msg.from_user.id,
#                 prompt=caption,
#                 model="sora2-i2v",
#                 aspect_ratio=ar,
#                 images_list=[file_url],
#             )
#         except Exception:
#             with contextlib.suppress(Exception): await processing.delete()
#             logger.exception("I2V enqueue failed")
#             await msg.answer("❌ Ошибка генерации видео: попробуйте переделать промт")
#             return

#         with contextlib.suppress(Exception): await processing.delete()
#         await state.clear()
#         await msg.answer(
#             "🎬 Видео начало создаваться. Это займёт несколько минут.\n"
#             "Я пришлю видео сюда, когда оно будет готово!"
#         )
#         return

#     # фото без подписи → сохраняем URL и просим текст
#     await state.update_data(photo_url=file_url)
#     await state.set_state(I2V.waiting_caption)
#     await msg.answer("✍🏻 Добавьте к фото описание (промт) одним сообщением")

# # ❗️ ВАЖНО: в waiting_photo игнорируем любые команды, чтобы не залипать
# @router.message(I2V.waiting_photo, F.text, ~F.text.regexp(r"^/"))
# async def reject_text_in_photo_mode(msg: Message, state: FSMContext):
#     await msg.answer("❌ Генерация по фото ожидает сообщение с фото и подписью. Пришлите фото с промтом в подписи.")

# @router.message(I2V.waiting_caption, F.text, ~F.text.regexp(r"^/"))
# async def got_caption_after_photo(msg: Message, state: FSMContext):
#     prompt = (msg.text or "").strip()
#     if len(prompt) > 2000:
#         await msg.answer("❌ Описание слишком длинное. Максимум 2000 символов."); return
#     if len(prompt) < 5:
#         await msg.answer("❌ Описание слишком короткое. Минимум 5 символов."); return

#     data = await state.get_data()
#     file_url = data.get("photo_url")
#     ar = data.get("ar", "9:16")
#     if not file_url:
#         await state.clear()
#         await msg.answer("📸 Отправьте изображение с подписью (это будет промт).")
#         return

#     processing = await msg.answer("🔄 Отправляем запрос на генерацию…")
#     try:
#         redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
#         await redis.enqueue_job(
#             "queue_generation",
#             telegram_id=msg.from_user.id,
#             prompt=prompt,
#             model="sora2-i2v",
#             aspect_ratio=ar,
#             images_list=[file_url],
#         )
#     except Exception:
#         with contextlib.suppress(Exception): await processing.delete()
#         logger.exception("I2V enqueue failed")
#         await msg.answer("❌ Ошибка генерации видео: попробуйте переделать промт")
#         return

#     with contextlib.suppress(Exception): await processing.delete()
#     await state.clear()
#     await msg.answer(
#         "🎬 Видео начало создаваться. Это займёт несколько минут.\n"
#         "Я пришлю видео сюда, когда оно будет готово!"
#     )

# # Опционально: /cancel снимает любое состояние
# @router.message(F.text.regexp(r"^/cancel$"))
# async def cancel_any(msg: Message, state: FSMContext):
#     await state.clear()
#     await msg.answer("✅ Ок, отменил. Можно начать заново.")


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
from app.bot.keyboards.common import kb_vertical_toggle
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
                [InlineKeyboardButton(text="💳 Купить генерации", callback_data="menu:packages")]
            ])
            await edit_or_send(cb, "❌ У вас недостаточно генераций(", reply_markup=kb)
            await safe_cb_answer(cb)
            return

        # дефолт: вертикально 9:16
        await state.update_data(ar="9:16", model="sora2-i2v")

        await edit_or_send(
            cb,
            "📸 Отправьте изображение.",
            reply_markup=kb_vertical_toggle(is_vertical=True),
        )
        await state.set_state(I2V.waiting_photo)
        await safe_cb_answer(cb)

@router.callback_query(I2V.waiting_photo, F.data == "toggle:ar")
async def toggle_ar(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ar = data.get("ar", "9:16")
    new_ar = "16:9" if ar == "9:16" else "9:16"
    await state.update_data(ar=new_ar)
    is_vertical = (new_ar == "9:16")
    await edit_or_send(
        cb,
        "📸 Отправьте изображение.",
        reply_markup=kb_vertical_toggle(is_vertical=is_vertical),
    )
    await safe_cb_answer(cb)

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

        data = await state.get_data()
        ar = data.get("ar", "9:16")

        processing = await msg.answer("🔄 Отправляем запрос на генерацию…")
        try:
            redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            await redis.enqueue_job(
                "queue_generation",
                telegram_id=msg.from_user.id,
                prompt=caption,
                model="sora2-i2v",
                aspect_ratio=ar,
                images_list=[file_url],
            )
        except Exception:
            with contextlib.suppress(Exception): await processing.delete()
            logger.exception("I2V enqueue failed")
            await msg.answer("❌ Ошибка генерации видео: попробуйте переделать промт")
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

# ❗️ ВАЖНО: в waiting_photo игнорируем любые команды, чтобы не залипать
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
    ar = data.get("ar", "9:16")
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
            aspect_ratio=ar,
            images_list=[file_url],
        )
    except Exception:
        with contextlib.suppress(Exception): await processing.delete()
        logger.exception("I2V enqueue failed")
        await msg.answer("❌ Ошибка генерации видео: попробуйте переделать промт")
        return

    with contextlib.suppress(Exception): await processing.delete()
    await state.clear()
    await msg.answer(
        "🎬 Видео начало создаваться. Это займёт несколько минут.\n"
        "Я пришлю видео сюда, когда оно будет готово!"
    )

# Опционально: /cancel снимает любое состояние
@router.message(F.text.regexp(r"^/cancel$"))
async def cancel_any(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✅ Ок, отменил. Можно начать заново.")