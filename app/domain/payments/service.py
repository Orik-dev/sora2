# app/domain/payments/service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Payment
from app.domain.users.service import add_credits

async def create_payment_record(
    session: AsyncSession, *,
    user_id: int, provider_payment_id: str, qty_credits: int, amount_rub: int
) -> int:
    p = Payment(
        user_id=user_id,
        provider_payment_id=provider_payment_id,
        qty_credits=qty_credits,
        amount_rub=amount_rub,
        status="pending",
    )
    session.add(p)
    await session.commit()
    return int(p.id)

async def mark_payment_succeeded(session: AsyncSession, provider_payment_id: str) -> None:
    row = await session.execute(select(Payment).where(Payment.provider_payment_id == provider_payment_id))
    p = row.scalars().first()
    if not p or p.status == "succeeded":
        return
    p.status = "succeeded"
    await session.commit()
    await add_credits(session, p.user_id, p.qty_credits)
