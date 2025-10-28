# # app/bot/handlers/payments.py
# from __future__ import annotations

# import re
# from decimal import Decimal
# from aiogram import Router, F, Dispatcher
# from aiogram.filters import Command
# from aiogram.types import (
#     CallbackQuery, Message, LabeledPrice, PreCheckoutQuery,
#     InlineKeyboardMarkup, InlineKeyboardButton,
# )
# from aiogram.utils.keyboard import InlineKeyboardBuilder

# from aiogram.fsm.state import StatesGroup, State
# from aiogram.fsm.context import FSMContext

# from app.core.settings import settings
# from app.core.db import SessionLocal
# from app.domain.users.service import get_or_create_user, get_balance, add_credits
# from app.domain.payments.service import create_payment_record
# from app.domain.payments.providers.yookassa import create_payment
# from app.models.models import Payment
# from app.utils.msg import edit_or_send
# from app.utils.tg import safe_cb_answer
# import logging

# logger = logging.getLogger(__name__)

# router = Router(name=__name__)

# # ──────────────────────────────────────────────────────────────────────────────
# # FSM: ждём e-mail только когда пользователь согласился на чек
# # ──────────────────────────────────────────────────────────────────────────────
# class ReceiptWait(StatesGroup):
#     email = State()

# EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# def register_payment_handlers(dp: Dispatcher) -> None:
#     dp.include_router(router)


# def _return_url() -> str:
#     return settings.webhook_base()

# # ──────────────────────────────────────────────────────────────────────────────
# # helpers (планы)
# # ──────────────────────────────────────────────────────────────────────────────
# def _plans_rub() -> dict:
#     return getattr(settings, "SUBSCRIPTION_PLANS_RUBS", {}) or {}

# def _plans_stars() -> dict:
#     return getattr(settings, "SUBSCRIPTION_PLANS_STARS", {}) or {}

# # ──────────────────────────────────────────────────────────────────────────────
# # keyboards
# # ──────────────────────────────────────────────────────────────────────────────
# def kb_methods() -> InlineKeyboardMarkup:
#     kb = InlineKeyboardBuilder()
#     if _plans_rub():
#         kb.button(text="💳 Карта РФ(₽)", callback_data="paymethod:rub")
#     if _plans_stars():
#         kb.button(text="⭐️ Звёзды", callback_data="paymethod:star")
#     # kb.button(text="⬅️ Назад", callback_data="menu:root")
#     kb.adjust(3)
#     return kb.as_markup()

# def kb_plans_rub() -> InlineKeyboardMarkup:
#     plans = _plans_rub()
#     kb = InlineKeyboardBuilder()
#     for key, plan in plans.items():
#         title = plan.get("name") or f"{plan.get('credits','')} генераций — {plan.get('price','')} ₽"
#         if plan.get("badge"):
#             title = f"{title} {plan['badge']}"
#         kb.button(text=title, callback_data=f"pay_rub:{key}")
#     kb.button(text="⬅️ Способы оплаты", callback_data="choose_methods")
#     kb.adjust(1)
#     return kb.as_markup()

# def kb_plans_stars() -> InlineKeyboardMarkup:
#     plans = _plans_stars()
#     kb = InlineKeyboardBuilder()
#     for key, plan in plans.items():
#         title = plan.get("name") or f"{plan.get('credits','')} генераций — {plan.get('stars','')} ⭐"
#         if plan.get("badge"):
#             title = f"{title} {plan['badge']}"
#         kb.button(text=title, callback_data=f"pay_star:{key}")
#     kb.button(text="⬅️ Способы оплаты", callback_data="choose_methods")
#     kb.adjust(1)
#     return kb.as_markup()

# def kb_receipt_choice(plan_key: str) -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="✅ Да, нужен чек", callback_data=f"receipt:yes:{plan_key}")],
#         [InlineKeyboardButton(text="🙅 Чек не нужен", callback_data=f"receipt:no:{plan_key}")],
#         [InlineKeyboardButton(text="⬅️ Способы оплаты", callback_data="choose_methods")],
#     ])

# # ──────────────────────────────────────────────────────────────────────────────
# # entry points (/buy и кнопки меню)
# # ──────────────────────────────────────────────────────────────────────────────
# @router.message(Command("buy"))
# async def cmd_buy(msg: Message, state: FSMContext):
#     await state.clear()
#     async with SessionLocal() as session:
#         await get_or_create_user(session, msg.from_user.id)
#         bal = await get_balance(session, msg.from_user.id)

#     text = (
#         f"💼 Баланс: <b>{bal}</b> генераций\n\n"
#         # "🌏 Если у вас нет возможности оплатить картой системы МИР,выберите оплату звёздочками\n\n"
#         "Выберите способ оплаты:"
#     )
#     await msg.answer(text, reply_markup=kb_methods(), parse_mode="HTML")

# @router.callback_query(F.data == "menu:packages")
# async def on_menu_packages(cb: CallbackQuery, state: FSMContext):
#     await state.clear()
#     async with SessionLocal() as session:
#         await get_or_create_user(session, cb.from_user.id)
#         bal = await get_balance(session, cb.from_user.id)

#     text = (
#         f"💼 Баланс: <b>{bal}</b> генераций\n\n"
#         # "🌏 Если у вас нет возможности оплатить картой системы МИР,выберите оплату звёздочками\n\n"
#         "Выберите способ оплаты:"
#     )
#     await edit_or_send(cb, text, reply_markup=kb_methods())
#     await safe_cb_answer(cb)

# @router.callback_query(F.data == "choose_methods")
# async def choose_methods(cb: CallbackQuery, state: FSMContext):
#     await state.clear()
#     await edit_or_send(cb, "Выберите способ оплаты:", reply_markup=kb_methods())
#     await safe_cb_answer(cb)

# @router.callback_query(F.data == "paymethod:rub")
# async def method_rub(cb: CallbackQuery, state: FSMContext):
#     await state.clear()
#     await edit_or_send(cb, "Выберите пакет генераций (₽):", reply_markup=kb_plans_rub())
#     await safe_cb_answer(cb)

# @router.callback_query(F.data == "paymethod:star")
# async def method_star(cb: CallbackQuery, state: FSMContext):
#     await state.clear()
#     await edit_or_send(cb, "Выберите пакет генераций (⭐⭐⭐⭐⭐):\n\n\n", reply_markup=kb_plans_stars())
#     await safe_cb_answer(cb)

# # ──────────────────────────────────────────────────────────────────────────────
# # общая функция создания платежа ₽
# # ──────────────────────────────────────────────────────────────────────────────
# async def _make_yoo_payment(cb: CallbackQuery, *, user, plan: dict, plan_key: str):
#     pay = await create_payment(
#         amount=Decimal(plan["price"]),
#         currency="RUB",
#         description=f"Veo 3 Studio: {plan['credits']} генераций",
#         return_url=_return_url(),
#         metadata={"telegram_id": cb.from_user.id, "plan": plan_key, "qty": plan["credits"]},
#         customer_email=getattr(user, "email", None),
#         receipt_opt_out=bool(getattr(user, "receipt_opt_out", 0)),
#     )

#     async with SessionLocal() as session:
#         await create_payment_record(
#             session,
#             user_id=user.user_id,
#             provider_payment_id=pay["payment_id"],
#             qty_credits=plan["credits"],
#             amount_rub=plan["price"],
#         )

#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Оплатить →", url=pay["payment_url"])],
#         [InlineKeyboardButton(text="⬅️ Способы оплаты", callback_data="menu:packages")],
#     ])
#     await edit_or_send(
#         cb,
#         f"Заказ: <b>{plan['credits']}</b> генераций • <b>{plan['price']} ₽</b>\n"
#         "Нажмите «Оплатить», затем вернитесь в бот — зачисление придёт автоматически.",
#         reply_markup=kb,
#     )

# # ──────────────────────────────────────────────────────────────────────────────
# # ₽ via YooKassa (с вопросом про чек)
# # ──────────────────────────────────────────────────────────────────────────────
# @router.callback_query(F.data.startswith("pay_rub:"))
# async def pay_rub(cb: CallbackQuery, state: FSMContext):
#     await safe_cb_answer(cb)
#     plan_key = cb.data.split(":", 1)[1]
#     plan = _plans_rub().get(plan_key)
#     if not plan:
#         await cb.message.answer("Пакет не найден")
#         return

#     async with SessionLocal() as session:
#         user = await get_or_create_user(session, cb.from_user.id)

#     # Если включены чеки и мы не знаем email/отказ — спросим один раз
#     if settings.YOOKASSA_RECEIPT_ENABLED and not getattr(user, "email", None) and not getattr(user, "receipt_opt_out", 0):
#         await state.set_state(ReceiptWait.email)
#         await state.update_data(plan_key=plan_key)
#         await edit_or_send(cb, "Нужен ли вам чек на e-mail?", reply_markup=kb_receipt_choice(plan_key))
#         return

#     await _make_yoo_payment(cb, user=user, plan=plan, plan_key=plan_key)

# # Пользователь выбрал «Чек не нужен»
# @router.callback_query(F.data.startswith("receipt:no:"))
# async def receipt_no(cb: CallbackQuery, state: FSMContext):
#     await safe_cb_answer(cb)
#     plan_key = cb.data.rsplit(":", 1)[1]
#     plan = _plans_rub().get(plan_key)
#     if not plan:
#         await cb.message.answer("Пакет не найден")
#         return

#     async with SessionLocal() as session:
#         user = await get_or_create_user(session, cb.from_user.id)
#         user.receipt_opt_out = 1
#         await session.commit()

#     await state.clear()
#     await _make_yoo_payment(cb, user=user, plan=plan, plan_key=plan_key)

# # Пользователь согласился на чек → просим e-mail и ждём его в состоянии
# @router.callback_query(F.data.startswith("receipt:yes:"))
# async def receipt_yes(cb: CallbackQuery, state: FSMContext):
#     await safe_cb_answer(cb)
#     plan_key = cb.data.rsplit(":", 1)[1]
#     await state.set_state(ReceiptWait.email)
#     await state.update_data(plan_key=plan_key)

#     await edit_or_send(
#         cb,
#         "💌 Пришлите ваш e-mail одним сообщением (пример: <b>name@example.com</b>).",
#         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
#             [InlineKeyboardButton(text="⬅️ Способы оплаты", callback_data="choose_methods")]
#         ]),
#     )

# # ──────────────────────────────────────────────────────────────────────────────
# # Ловим e-mail ТОЛЬКО в состоянии ReceiptWait.email
# # ──────────────────────────────────────────────────────────────────────────────
# @router.message(ReceiptWait.email, F.text.regexp(EMAIL_RE))
# async def email_ok(msg: Message, state: FSMContext):
#     data = await state.get_data()
#     plan_key = (data or {}).get("plan_key")
#     plan = _plans_rub().get(plan_key or "")
#     if not plan:
#         await state.clear()
#         await msg.answer("Пакет не найден, начните заново: /buy", parse_mode="HTML")
#         return

#     email = (msg.text or "").strip()

#     # сохраняем почту у пользователя
#     async with SessionLocal() as session:
#         user = await get_or_create_user(session, msg.from_user.id)
#         user.email = email
#         await session.commit()

#     await state.clear()

#     # создаём платёж и присылаем ссылку
#     pay = await create_payment(
#         amount=Decimal(plan["price"]),
#         currency="RUB",
#         description=f"Sora 2: {plan['credits']} генераций",
#         return_url=_return_url(),
#         metadata={"telegram_id": msg.from_user.id, "plan": plan_key, "qty": plan["credits"]},
#         customer_email=email,
#         receipt_opt_out=False,
#     )

#     async with SessionLocal() as session:
#         await create_payment_record(
#             session,
#             user_id=user.user_id,
#             provider_payment_id=pay["payment_id"],
#             qty_credits=plan["credits"],
#             amount_rub=plan["price"],
#         )

#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Оплатить →", url=pay["payment_url"])],
#         [InlineKeyboardButton(text="⬅️ Способы оплаты", callback_data="choose_methods")],
#     ])
#     await msg.answer(
#         f"Заказ: <b>{plan['credits']}</b> генераций • <b>{plan['price']} ₽</b>\n"
#         "Нажмите «Оплатить», затем вернитесь в бот — зачисление придёт автоматически.",
#         reply_markup=kb,
#         parse_mode="HTML",
#     )

# @router.message(ReceiptWait.email, F.text)
# async def email_bad(msg: Message):
#     await msg.answer(
#         "Похоже, это не e-mail. Попробуйте ещё раз.\nНапример: <b>name@example.com</b>",
#         parse_mode="HTML",
#     )

# # ──────────────────────────────────────────────────────────────────────────────
# # Stars (XTR) — как было
# # ──────────────────────────────────────────────────────────────────────────────
# @router.callback_query(F.data.startswith("pay_star:"))
# async def pay_star(cb: CallbackQuery, state: FSMContext):
#     await state.clear()
#     await safe_cb_answer(cb)
#     key = cb.data.split(":", 1)[1]
#     plan = _plans_stars().get(key)
#     if not plan:
#         await cb.message.answer("Пакет не найден")
#         return

#     logger.info(f"Creating Stars invoice for user {cb.from_user.id}, plan {key}")  # ← ЛОГ
    
#     prices = [LabeledPrice(label=plan.get("name", "Покупка ⭐"), amount=int(plan["stars"]))]
    
#     try:
#         await cb.message.delete()
#     except Exception as e:
#         logger.warning(f"Could not delete message: {e}")
    
#     try:
#         await cb.bot.send_invoice(
#             chat_id=cb.from_user.id,
#             title=plan.get("name", "Пакет генераций"),
#             description=f"{plan['credits']} генераций",
#             payload=f"star:{key}",
#             provider_token="",
#             currency="XTR",
#             prices=prices,
#         )
#         logger.info(f"Invoice sent successfully to {cb.from_user.id}")  # ← ЛОГ
#     except Exception as e:
#         logger.error(f"Failed to send invoice: {e}", exc_info=True)  # ← ЛОГ
#         await cb.bot.send_message(cb.from_user.id, "Не удалось создать счёт. Попробуйте позже.")

# @router.pre_checkout_query()
# async def pre_checkout(q: PreCheckoutQuery):
#     """Обрабатываем pre-checkout для Stars платежей"""
#     try:
#         logger.info(f"Pre-checkout query from {q.from_user.id}, payload: {q.invoice_payload}")
        
#         # Проверяем что это наш платёж
#         if not q.invoice_payload or not q.invoice_payload.startswith("star:"):
#             logger.warning(f"Unknown payload: {q.invoice_payload}")
#             await q.answer(ok=False, error_message="Неизвестный тип платежа")
#             return
        
#         # Проверяем что план существует
#         key = q.invoice_payload.split(":", 1)[1] if ":" in q.invoice_payload else ""
#         plan = _plans_stars().get(key)
        
#         if not plan:
#             logger.error(f"Plan not found: {key}")
#             await q.answer(ok=False, error_message="План не найден")
#             return
        
#         # Всё ок, подтверждаем
#         logger.info(f"Approving pre-checkout for user {q.from_user.id}, plan {key}")
#         await q.answer(ok=True)
        
#     except Exception as e:
#         logger.error(f"Pre-checkout error: {e}", exc_info=True)
#         await q.answer(ok=False, error_message="Ошибка обработки платежа")

# @router.message(F.successful_payment)
# async def on_success(msg: Message, state: FSMContext):
#     await state.clear()
#     sp = msg.successful_payment
#     payload = (sp.invoice_payload or "")
    
#     # Проверяем, что это Stars платёж
#     if not payload.startswith("star:"):
#         return
    
#     # Извлекаем ключ плана
#     key = payload.split(":", 1)[1] if ":" in payload else ""
#     plan = _plans_stars().get(key)
    
#     if not plan:
#         await msg.answer("❌ Ошибка: план не найден", parse_mode="HTML")
#         return
    
#     credits = int(plan["credits"])

#     async with SessionLocal() as session:
#         # Начисляем кредиты
#         await add_credits(session, telegram_id=msg.from_user.id, qty=credits)

#         # Сохраняем платёж
#         charge_id = sp.telegram_payment_charge_id or sp.provider_payment_charge_id
#         total_amount = int(sp.total_amount or 0)

#         session.add(Payment(
#             user_id=msg.from_user.id,
#             provider_payment_id=charge_id,
#             qty_credits=credits,
#             amount_rub=0,
#             status="paid",
#         ))
#         await session.commit()

#     await msg.answer(
#         f"✅ Оплата прошла! Начислено <b>{credits}</b> генераций.\n"
#         f"Тип: Stars · Сумма: {total_amount} ⭐",
#         parse_mode="HTML",
#     )

# app/bot/handlers/payments.py
from __future__ import annotations

import re
from decimal import Decimal
from aiogram import Router, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from app.core.settings import settings
from app.core.db import SessionLocal
from app.domain.users.service import get_or_create_user, get_balance, add_credits
from app.domain.payments.service import create_payment_record
from app.domain.payments.providers.yookassa import create_payment
from app.models.models import Payment
from app.utils.msg import edit_or_send
from app.utils.tg import safe_cb_answer
import logging

logger = logging.getLogger(__name__)

router = Router(name=__name__)

class ReceiptWait(StatesGroup):
    email = State()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def register_payment_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)

def _return_url() -> str:
    return settings.webhook_base()

def _plans_rub() -> dict:
    return getattr(settings, "SUBSCRIPTION_PLANS_RUBS", {}) or {}

def _plans_stars() -> dict:
    return getattr(settings, "SUBSCRIPTION_PLANS_STARS", {}) or {}

def kb_methods() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if _plans_rub():
        kb.button(text="💳 Карта РФ(₽)", callback_data="paymethod:rub")
    if _plans_stars():
        kb.button(text="⭐️ Звёзды", callback_data="paymethod:star")
    kb.adjust(3)
    return kb.as_markup()

def kb_plans_rub() -> InlineKeyboardMarkup:
    plans = _plans_rub()
    kb = InlineKeyboardBuilder()
    for key, plan in plans.items():
        title = plan.get("name") or f"{plan.get('credits','')} генераций — {plan.get('price','')} ₽"
        if plan.get("badge"):
            title = f"{title} {plan['badge']}"
        kb.button(text=title, callback_data=f"pay_rub:{key}")
    kb.button(text="⬅️ Способы оплаты", callback_data="choose_methods")
    kb.adjust(1)
    return kb.as_markup()

def kb_plans_stars() -> InlineKeyboardMarkup:
    plans = _plans_stars()
    kb = InlineKeyboardBuilder()
    for key, plan in plans.items():
        title = plan.get("name") or f"{plan.get('credits','')} генераций — {plan.get('stars','')} ⭐"
        if plan.get("badge"):
            title = f"{title} {plan['badge']}"
        kb.button(text=title, callback_data=f"pay_star:{key}")
    kb.button(text="⬅️ Способы оплаты", callback_data="choose_methods")
    kb.adjust(1)
    return kb.as_markup()

def kb_receipt_choice(plan_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, нужен чек", callback_data=f"receipt:yes:{plan_key}")],
        [InlineKeyboardButton(text="🙅 Чек не нужен", callback_data=f"receipt:no:{plan_key}")],
        [InlineKeyboardButton(text="⬅️ Способы оплаты", callback_data="choose_methods")],
    ])

@router.message(Command("buy"))
async def cmd_buy(msg: Message, state: FSMContext):
    await state.clear()
    async with SessionLocal() as session:
        await get_or_create_user(session, msg.from_user.id)
        bal = await get_balance(session, msg.from_user.id)

    text = (
        f"💼 Баланс: <b>{bal}</b> генераций\n\n"
        "Выберите способ оплаты:"
    )
    await msg.answer(text, reply_markup=kb_methods(), parse_mode="HTML")

@router.callback_query(F.data == "menu:packages")
async def on_menu_packages(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    async with SessionLocal() as session:
        await get_or_create_user(session, cb.from_user.id)
        bal = await get_balance(session, cb.from_user.id)

    text = (
        f"💼 Баланс: <b>{bal}</b> генераций\n\n"
        "Выберите способ оплаты:"
    )
    await edit_or_send(cb, text, reply_markup=kb_methods())
    await safe_cb_answer(cb)

@router.callback_query(F.data == "choose_methods")
async def choose_methods(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_or_send(cb, "Выберите способ оплаты:", reply_markup=kb_methods())
    await safe_cb_answer(cb)

@router.callback_query(F.data == "paymethod:rub")
async def method_rub(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_or_send(cb, "Выберите пакет генераций (₽):", reply_markup=kb_plans_rub())
    await safe_cb_answer(cb)

@router.callback_query(F.data == "paymethod:star")
async def method_star(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_or_send(cb, "Выберите пакет генераций (⭐⭐⭐⭐⭐):\n\n\n", reply_markup=kb_plans_stars())
    await safe_cb_answer(cb)

async def _make_yoo_payment(cb: CallbackQuery, *, user, plan: dict, plan_key: str):
    pay = await create_payment(
        amount=Decimal(plan["price"]),
        currency="RUB",
        description=f"Veo 3 Studio: {plan['credits']} генераций",
        return_url=_return_url(),
        metadata={"telegram_id": cb.from_user.id, "plan": plan_key, "qty": plan["credits"]},
        customer_email=getattr(user, "email", None),
        receipt_opt_out=bool(getattr(user, "receipt_opt_out", 0)),
    )

    async with SessionLocal() as session:
        await create_payment_record(
            session,
            user_id=user.user_id,
            provider_payment_id=pay["payment_id"],
            qty_credits=plan["credits"],
            amount_rub=plan["price"],
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить →", url=pay["payment_url"])],
        [InlineKeyboardButton(text="⬅️ Способы оплаты", callback_data="menu:packages")],
    ])
    await edit_or_send(
        cb,
        f"Заказ: <b>{plan['credits']}</b> генераций • <b>{plan['price']} ₽</b>\n"
        "Нажмите «Оплатить», затем вернитесь в бот — зачисление придёт автоматически.",
        reply_markup=kb,
    )

@router.callback_query(F.data.startswith("pay_rub:"))
async def pay_rub(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    plan_key = cb.data.split(":", 1)[1]
    plan = _plans_rub().get(plan_key)
    if not plan:
        await cb.message.answer("Пакет не найден")
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(session, cb.from_user.id)

    if settings.YOOKASSA_RECEIPT_ENABLED and not getattr(user, "email", None) and not getattr(user, "receipt_opt_out", 0):
        await state.set_state(ReceiptWait.email)
        await state.update_data(plan_key=plan_key)
        await edit_or_send(cb, "Нужен ли вам чек на e-mail?", reply_markup=kb_receipt_choice(plan_key))
        return

    await _make_yoo_payment(cb, user=user, plan=plan, plan_key=plan_key)

@router.callback_query(F.data.startswith("receipt:no:"))
async def receipt_no(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    plan_key = cb.data.rsplit(":", 1)[1]
    plan = _plans_rub().get(plan_key)
    if not plan:
        await cb.message.answer("Пакет не найден")
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(session, cb.from_user.id)
        user.receipt_opt_out = 1
        await session.commit()

    await state.clear()
    await _make_yoo_payment(cb, user=user, plan=plan, plan_key=plan_key)

@router.callback_query(F.data.startswith("receipt:yes:"))
async def receipt_yes(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    plan_key = cb.data.rsplit(":", 1)[1]
    await state.set_state(ReceiptWait.email)
    await state.update_data(plan_key=plan_key)

    await edit_or_send(
        cb,
        "💌 Пришлите ваш e-mail одним сообщением (пример: <b>name@example.com</b>).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Способы оплаты", callback_data="choose_methods")]
        ]),
    )

@router.message(ReceiptWait.email, F.text.regexp(EMAIL_RE))
async def email_ok(msg: Message, state: FSMContext):
    data = await state.get_data()
    plan_key = (data or {}).get("plan_key")
    plan = _plans_rub().get(plan_key or "")
    if not plan:
        await state.clear()
        await msg.answer("Пакет не найден, начните заново: /buy", parse_mode="HTML")
        return

    email = (msg.text or "").strip()

    async with SessionLocal() as session:
        user = await get_or_create_user(session, msg.from_user.id)
        user.email = email
        await session.commit()

    await state.clear()

    pay = await create_payment(
        amount=Decimal(plan["price"]),
        currency="RUB",
        description=f"Sora 2: {plan['credits']} генераций",
        return_url=_return_url(),
        metadata={"telegram_id": msg.from_user.id, "plan": plan_key, "qty": plan["credits"]},
        customer_email=email,
        receipt_opt_out=False,
    )

    async with SessionLocal() as session:
        await create_payment_record(
            session,
            user_id=user.user_id,
            provider_payment_id=pay["payment_id"],
            qty_credits=plan["credits"],
            amount_rub=plan["price"],
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить →", url=pay["payment_url"])],
        [InlineKeyboardButton(text="⬅️ Способы оплаты", callback_data="choose_methods")],
    ])
    await msg.answer(
        f"Заказ: <b>{plan['credits']}</b> генераций • <b>{plan['price']} ₽</b>\n"
        "Нажмите «Оплатить», затем вернитесь в бот — зачисление придёт автоматически.",
        reply_markup=kb,
        parse_mode="HTML",
    )

@router.message(ReceiptWait.email, F.text)
async def email_bad(msg: Message):
    await msg.answer(
        "Похоже, это не e-mail. Попробуйте ещё раз.\nНапример: <b>name@example.com</b>",
        parse_mode="HTML",
    )

# ============= STARS PAYMENT (FIXED) =============

@router.callback_query(F.data.startswith("pay_star:"))
async def pay_star(cb: CallbackQuery, state: FSMContext):
    """Отправляем invoice для Stars-платежа"""
    await state.clear()
    await safe_cb_answer(cb)
    
    key = cb.data.split(":", 1)[1]
    plan = _plans_stars().get(key)
    if not plan:
        await cb.message.answer("❌ Пакет не найден")
        return

    logger.info(f"Creating Stars invoice: user={cb.from_user.id}, plan={key}")
    
    # Удаляем предыдущее сообщение
    try:
        await cb.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete message: {e}")
    
    # Отправляем invoice
    try:
        await cb.bot.send_invoice(
            chat_id=cb.from_user.id,
            title=plan.get("name", "Пакет генераций"),
            description=f"Получите {plan['credits']} генераций для создания видео",
            payload=f"star:{key}",
            provider_token="",  # Для XTR пустая строка
            currency="XTR",
            prices=[LabeledPrice(label=plan.get("name", "Генерации"), amount=int(plan["stars"]))],
            # Важно: НЕ указываем reply_markup - Telegram автоматически добавит кнопку Pay
        )
        logger.info(f"✅ Invoice sent successfully to {cb.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Failed to send invoice: {e}", exc_info=True)
        await cb.bot.send_message(
            cb.from_user.id, 
            "❌ Не удалось создать счёт. Попробуйте позже или выберите другой способ оплаты.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Способы оплаты", callback_data="choose_methods")]
            ])
        )

@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    """Подтверждаем pre-checkout для Stars"""
    try:
        logger.info(f"Pre-checkout: user={q.from_user.id}, payload={q.invoice_payload}")
        
        # Проверяем payload
        if not q.invoice_payload or not q.invoice_payload.startswith("star:"):
            logger.warning(f"Invalid payload: {q.invoice_payload}")
            await q.answer(ok=False, error_message="❌ Неизвестный тип платежа")
            return
        
        # Проверяем план
        key = q.invoice_payload.split(":", 1)[1] if ":" in q.invoice_payload else ""
        plan = _plans_stars().get(key)
        
        if not plan:
            logger.error(f"Plan not found: {key}")
            await q.answer(ok=False, error_message="❌ План не найден")
            return
        
        # Всё ОК - подтверждаем
        logger.info(f"✅ Pre-checkout approved: user={q.from_user.id}, plan={key}")
        await q.answer(ok=True)
        
    except Exception as e:
        logger.error(f"Pre-checkout error: {e}", exc_info=True)
        await q.answer(ok=False, error_message="❌ Ошибка обработки платежа")

@router.message(F.successful_payment)
async def on_success(msg: Message, state: FSMContext):
    """Обрабатываем успешный Stars-платёж"""
    await state.clear()
    sp = msg.successful_payment
    payload = (sp.invoice_payload or "")
    
    logger.info(f"Successful payment: user={msg.from_user.id}, payload={payload}, amount={sp.total_amount}")
    
    # Проверяем Stars
    if not payload.startswith("star:"):
        logger.warning(f"Non-star payment received: {payload}")
        return
    
    # Извлекаем план
    key = payload.split(":", 1)[1] if ":" in payload else ""
    plan = _plans_stars().get(key)
    
    if not plan:
        await msg.answer("❌ Ошибка: план не найден. Обратитесь в поддержку.", parse_mode="HTML")
        return
    
    credits = int(plan["credits"])

    async with SessionLocal() as session:
        # Начисляем кредиты
        await add_credits(session, telegram_id=msg.from_user.id, qty=credits)

        # Сохраняем платёж
        charge_id = sp.telegram_payment_charge_id or sp.provider_payment_charge_id
        total_amount = int(sp.total_amount or 0)

        session.add(Payment(
            user_id=msg.from_user.id,
            provider_payment_id=charge_id,
            qty_credits=credits,
            amount_rub=0,
            status="paid",
        ))
        await session.commit()
        
        # Получаем новый баланс
        new_balance = await get_balance(session, msg.from_user.id)

    await msg.answer(
        f"✅ Оплата прошла успешно!\n\n"
        f"➕ Начислено: <b>{credits}</b> генераций\n"
        f"💰 Ваш баланс: <b>{new_balance}</b> генераций\n"
        f"⭐ Оплачено: {total_amount} Stars\n\n"
        f"Создать видео: /create_video",
        parse_mode="HTML",
    )
    
    logger.info(f"✅ Payment processed: user={msg.from_user.id}, credits={credits}, new_balance={new_balance}")