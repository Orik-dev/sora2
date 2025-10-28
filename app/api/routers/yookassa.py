from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.repo.db import get_session
from app.models.models import Payment as DbPayment, User
from app.domain.users.service import add_credits
from app.bot.init import bot

router = APIRouter()

@router.post("/yookassa")
async def yookassa_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    if body.get("event") != "payment.succeeded":
        return {"ok": False}

    pid = body.get("object", {}).get("id")
    if not pid:
        return {"ok": False}

    q = await session.execute(select(DbPayment).where(DbPayment.provider_payment_id == pid))
    payment = q.scalars().first()
    if not payment:
        return {"ok": True}

    if payment.status != "succeeded":
        payment.status = "succeeded"
        await add_credits(session, payment.user_id, payment.qty_credits)
        await session.commit()

        user = await session.execute(select(User).where(User.user_id == payment.user_id))
        user = user.scalars().first()
        if user:
            try:
                await bot.send_message(
                    chat_id=user.user_id,
                    text=(
                        "💳 Оплата получена!\n"
                        f"➕ Начислено: {payment.qty_credits} генераций.\n"
                        f"💰 Текущий баланс: {user.credits}\n"
                        f"Создать видео: /create_video\n"
                    )
                )
            except Exception:
                pass

    return {"ok": True}
