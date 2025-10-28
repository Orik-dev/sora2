# app/bot/handlers/start.py
from __future__ import annotations

from aiogram import Router, F, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy import update

from app.core.db import SessionLocal
from app.core.settings import settings
from app.bot.i18n import t, _load_locales, get_user_lang
from app.bot.keyboards.common import kb_language, kb_generate_type, kb_main
from app.utils.msg import edit_or_send
from app.utils.tg import safe_cb_answer
from app.domain.users.service import (
    upsert_from_message,
    set_locale,
    get_or_create_user,
    get_balance,
)
from app.models.models import User

router = Router(name=__name__)

# Невидимый символ: иногда нужен для пустых сообщений в TG
_ZWJ = "\u2060"


def register_start_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)


# @router.message(CommandStart())
# async def on_start(msg: Message):
#     # очищаем возможные «залипшие» состояния при старте
#     if msg.bot and hasattr(msg.bot, "fsm"):
#         try:
#             await msg.bot.fsm.storage.close()
#         except Exception:
#             pass

#     async with SessionLocal() as session:
#         await upsert_from_message(session, msg)
#         bundles = _load_locales()

#     await msg.answer(bundles["ru"]["lang.choose"], reply_markup=kb_language())


# @router.callback_query(F.data.startswith("lang:"))
# async def on_set_lang(cb: CallbackQuery):
#     lang = cb.data.split(":")[1]

#     async with SessionLocal() as session:
#         # сохраняем локаль
#         await set_locale(session, cb.from_user.id, lang)
#         # гарантируем пользователя и берём баланс
       
#     bundles = _load_locales()
#     strings = bundles["ru"] if lang == "ru" else bundles["en"]

#     # Приветственный текст (без хардкода «0»)
#     if lang == "ru":
#         caption = (
#             "👋 Добро пожаловать!\n"
#             "Это бот для генерации уникальных видео со звуком с помощью нейросети Sora 2.\n\n"
#             "✨ Просто отправьте описание (промт) того, какое видео вы хотите создать.\n"
#             "📸 Можно прикрепить фото — тогда видео будет сгенерировано с учётом изображения.\n\n"
#             "Нажмите «Создать видео» ниже, чтобы начать.\n\n"
#             'Пользуясь ботом, Вы принимаете наше <a href="https://example.com">пользовательское соглашение</a> и '
#             '<a href="https://telegram.org/privacy-tpa">политику конфиденциальности</a>.'
#         )
#     else:
#         caption = (
#             "👋 Welcome!\n"
#             "This bot generates unique videos with sound using the Sora 2 model.\n\n"
#             "✨ Just send a description (prompt) of the video you want to create.\n"
#             "📸 You can attach a photo — the video will be generated based on the image.\n\n"
#             "Tap “Create video” below to start.\n\n"
#             'By using this bot, you agree to our <a href="https://example.com/user-agreement">User Agreement</a> and '
#             '<a href="https://example.com/privacy-policy">Privacy Policy</a>.'
#         )

#     # отправляем анимацию, если задан путь; иначе — текст
#     sent = False
#     try:
#         if getattr(settings, "GREETING_VIDEO_PATH", None):
#             anim = FSInputFile(settings.GREETING_VIDEO_PATH)
#             await cb.message.answer_animation(
#                 animation=anim,
#                 caption=caption,
#                 reply_markup=kb_main(strings),
#                 parse_mode="HTML",
#                 disable_web_page_preview=True,
#             )
#             sent = True
#         elif getattr(settings, "GREETING_IMAGE_PATH", None):
#             img = FSInputFile(settings.GREETING_IMAGE_PATH)
#             await cb.message.answer_photo(
#                 photo=img,
#                 caption=caption,
#                 reply_markup=kb_main(strings),
#                 parse_mode="HTML",
#                 disable_web_page_preview=True,
#             )
#             sent = True
#         elif getattr(settings, "GREETING_IMAGE_URL", None):
#             await cb.message.answer_photo(
#                 photo=settings.GREETING_IMAGE_URL,
#                 caption=caption,
#                 reply_markup=kb_main(strings),
#                 parse_mode="HTML",
#                 disable_web_page_preview=True,
#             )
#             sent = True
#     except Exception:
#         pass

#     if not sent:
#         await edit_or_send(cb, caption, reply_markup=kb_main(strings))

#     await safe_cb_answer(cb)

@router.message(CommandStart())
async def on_start(msg: Message):
    # очищаем возможные «залипшие» состояния при старте
    if msg.bot and hasattr(msg.bot, "fsm"):
        try:
            await msg.bot.fsm.storage.close()
        except Exception:
            pass

    async with SessionLocal() as session:
        await upsert_from_message(session, msg)
        
        # Устанавливаем русский язык по умолчанию
        await set_locale(session, msg.from_user.id, "ru")
        
        bundles = _load_locales()
        strings = bundles["ru"]

    # ЗАКОММЕНТИРОВАНО: Выбор языка
    # await msg.answer(bundles["ru"]["lang.choose"], reply_markup=kb_language())
    
    # Сразу показываем приветственное сообщение на русском
    caption = (
        "👋 Добро пожаловать!\n"
        "Это бот для генерации уникальных видео со звуком с помощью нейросети Sora 2.\n\n"
        "✨ Просто отправьте описание (промт) того, какое видео вы хотите создать.\n"
        "📸 Можно прикрепить фото — тогда видео будет сгенерировано с учётом изображения.\n\n"
        "Нажмите «Создать видео» ниже, чтобы начать.\n\n"
        'Пользуясь ботом, Вы принимаете наше <a href="https://example.com">пользовательское соглашение</a> и '
        '<a href="https://telegram.org/privacy-tpa">политику конфиденциальности</a>.'
    )

    # отправляем анимацию, если задан путь; иначе — текст
    sent = False
    try:
        if getattr(settings, "GREETING_VIDEO_PATH", None):
            anim = FSInputFile(settings.GREETING_VIDEO_PATH)
            await msg.answer_animation(
                animation=anim,
                caption=caption,
                reply_markup=kb_main(strings),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            sent = True
        elif getattr(settings, "GREETING_IMAGE_PATH", None):
            img = FSInputFile(settings.GREETING_IMAGE_PATH)
            await msg.answer_photo(
                photo=img,
                caption=caption,
                reply_markup=kb_main(strings),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            sent = True
        elif getattr(settings, "GREETING_IMAGE_URL", None):
            await msg.answer_photo(
                photo=settings.GREETING_IMAGE_URL,
                caption=caption,
                reply_markup=kb_main(strings),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            sent = True
    except Exception:
        pass

    if not sent:
        await msg.answer(caption, reply_markup=kb_main(strings), parse_mode="HTML")


@router.callback_query(F.data == "menu:generate")
async def on_menu_generate(cb: CallbackQuery):
    async with SessionLocal() as session:
        # всегда гарантируем юзера и берём баланс одинаково, как в /buy
        user = await get_or_create_user(session, cb.from_user.id)


        # синхроним username при наличии колонки
        try:
            if hasattr(User, "username"):
                tg_username = cb.from_user.username or None
                if tg_username and tg_username != getattr(user, "username", None):
                    await session.execute(
                        update(User)
                        .where(User.user_id == cb.from_user.id)
                        .values(username=tg_username)
                    )
                    await session.commit()
                    user.username = tg_username
        except Exception:
            pass

        bundles = _load_locales()
        lang = await get_user_lang(session, cb.from_user.id)
        strings = bundles["ru"] if lang == "ru" else bundles["en"]

        name = (
            getattr(user, "username", None)
            or cb.from_user.username
            or cb.from_user.full_name
            or cb.from_user.first_name
            or ("друг" if lang == "ru" else "friend")
        )
        
        user = await get_or_create_user(session, cb.from_user.id)
        bal = await get_balance(session, cb.from_user.id)


        if lang == "ru":
            txt = (
                f"👋 Привет, {name}!\n"
                f"💰 Ваш баланс: <b>{bal}</b> генераций\n\n"
                "🎬 Sora 2 — нейросеть для генерации видео 10 секунд со звуком.\n"
            )
        else:
            txt = (
                f"👋 Hi, {name}!\n"
                f"💰 Your balance: <b>{bal}</b> generations\n\n"
                "🎬 Sora 2 generates 10-second videos with sound.\n"
            )

    await cb.message.answer(txt, reply_markup=kb_generate_type(strings), parse_mode="HTML")
    await safe_cb_answer(cb)


@router.callback_query(F.data == "menu:root")
async def on_menu_root(cb: CallbackQuery):
    async with SessionLocal() as session:
        bundles = _load_locales()
        try:
            lang = await get_user_lang(session, cb.from_user.id)
        except Exception:
            lang = "ru"

        strings = {**(bundles["ru"] if lang == "ru" else bundles["en"])}

        if settings.EXAMPLES_URL:
            strings["menu.examples.url"] = settings.EXAMPLES_URL
        if settings.GUIDE_URL:
            strings["menu.guide.url"] = settings.GUIDE_URL
        if settings.SUPPORT_URL:
            strings["menu.support.url"] = settings.SUPPORT_URL

        title = await t(session, cb.from_user.id, "menu.title")

    await edit_or_send(cb, title)
    await safe_cb_answer(cb)


@router.message(Command("create_video"))
async def on_create_video(msg: Message):
    async with SessionLocal() as session:
        bundles = _load_locales()
        try:
            lang = await get_user_lang(session, msg.from_user.id)
        except Exception:
            lang = "ru"
        strings = bundles["ru"] if lang == "ru" else bundles["en"]

        user = await get_or_create_user(session, msg.from_user.id)

        try:
            if hasattr(User, "username"):
                tg_username = msg.from_user.username or None
                if tg_username and tg_username != getattr(user, "username", None):
                    await session.execute(
                        update(User)
                        .where(User.user_id == msg.from_user.id)
                        .values(username=tg_username)
                    )
                    await session.commit()
                    user.username = tg_username
        except Exception:
            pass

        bal = await get_balance(session, msg.from_user.id)

        if lang == "ru":
            txt = (
                # f"💰 Ваш баланс: <b>{bal}</b> генераций\n\n"
                "🎬 Sora 2 — нейросеть для генерации видео 10-секунд со звуком.\n\n"
            )
        else:
            txt = (
                # f"💰 Your balance: <b>{bal}</b> generations\n\n"
                "🎬 Sora 2 generates 10-second videos with sound.\n\n"
            )

    await msg.answer(txt, reply_markup=kb_generate_type(strings), parse_mode="HTML")


@router.message(Command("menu"))
async def on_menu_cmd(msg: Message):
    async with SessionLocal() as session:
        bundles = _load_locales()
        try:
            lang = await get_user_lang(session, msg.from_user.id)
        except Exception:
            lang = "ru"

        strings = {**(bundles["ru"] if lang == "ru" else bundles["en"])}

        if settings.EXAMPLES_URL:
            strings["menu.examples.url"] = settings.EXAMPLES_URL
        if settings.GUIDE_URL:
            strings["menu.guide.url"] = settings.GUIDE_URL
        if settings.SUPPORT_URL:
            strings["menu.support.url"] = settings.SUPPORT_URL

        title = await t(session, msg.from_user.id, "menu.title")

    await msg.answer(title)


@router.message(Command("help"))
async def on_help_cmd(msg: Message):
    async with SessionLocal() as session:
        bundles = _load_locales()
        try:
            lang = await get_user_lang(session, msg.from_user.id)
        except Exception:
            lang = "ru"
        strings = bundles["ru"] if lang == "ru" else bundles["en"]

    text = f"{strings['menu.guide']}\n{strings['menu.support']}"
    await msg.answer(text)


@router.callback_query(F.data == "start:create_video")
async def on_create_video_button(cb: CallbackQuery):
    await on_create_video(cb.message)
    await safe_cb_answer(cb)
