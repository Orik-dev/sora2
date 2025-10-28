from __future__ import annotations

from aiogram import Router, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.utils.tg import safe_cb_answer

router = Router(name=__name__)

EXAMPLES_URL = "https://t.me/sora_promt"
SUPPORT_URL = "https://t.me/guard_gpt"

def register_example_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)

@router.message(F.text == "/example")
async def cmd_example(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Открыть примеры", url=EXAMPLES_URL)]
    ])
    await msg.answer("Наши примеры работ:", reply_markup=kb, disable_web_page_preview=True)

# если нужно вызывать из меню по callback
@router.callback_query(F.data == "menu:examples")
async def menu_examples(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Открыть примеры", url=EXAMPLES_URL)],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="menu:root")],
    ])
    await cb.message.edit_text("Наши примеры работ:", reply_markup=kb, disable_web_page_preview=True)
    await safe_cb_answer(cb)

# опционально: команда на саппорт (кнопка с прямым переходом)
@router.message(F.text == "/support")
async def cmd_support(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать в саппорт", url=SUPPORT_URL)]
    ])
    await msg.answer("Нужна помощь? Напишите нашему саппорту:", reply_markup=kb, disable_web_page_preview=True)
