import asyncio
from decimal import Decimal
from yookassa import Payment, Configuration
from app.core.settings import settings
from app.core.logger import logger

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

def _payload_with_receipt(
    amount: Decimal,
    currency: str,
    description: str,
    return_url: str,
    metadata: dict,
    *,
    email: str | None,
    receipt_enabled: bool,
) -> dict:
    base = {
        "amount": {"value": f"{amount:.2f}", "currency": currency},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
    }
    # Чек добавляем только если явно включён и есть email
    if receipt_enabled and email:
        base["receipt"] = {
            "customer": {"email": email},
            "items": [{
                "description": "Услуги по генерации видео",
                "quantity": "1.00",
                "amount": {"value": f"{amount:.2f}", "currency": currency},
                "vat_code": settings.VAT_CODE,
                "payment_subject": "service",
                "payment_mode": "full_prepayment",
            }],
            "tax_system_code": settings.TAX_SYSTEM_CODE,
        }
    return base

async def create_payment(
    *,
    amount: Decimal,
    currency: str,
    description: str,
    return_url: str,
    metadata: dict,
    customer_email: str | None,
    receipt_opt_out: bool,
) -> dict:
    """
    Создаёт платёж в YooKassa и возвращает {payment_id, payment_url}.
    Логика чеков:
      - если включено YOOKASSA_RECEIPT_ENABLED:
          - если пользователь отказался (receipt_opt_out=True) → шлём чек на RECEIPT_FALLBACK_EMAIL
          - иначе используем customer_email
      - если выключено → чек не отправляем вовсе.
    """
    email_for_receipt = None
    if settings.YOOKASSA_RECEIPT_ENABLED:
        if receipt_opt_out:
            email_for_receipt = settings.RECEIPT_FALLBACK_EMAIL
        else:
            email_for_receipt = customer_email

    payload = _payload_with_receipt(
        amount, currency, description, return_url, metadata,
        email=email_for_receipt,
        receipt_enabled=settings.YOOKASSA_RECEIPT_ENABLED,
    )

    def _create_sync():
        return Payment.create(payload)

    try:
        payment = await asyncio.to_thread(_create_sync)
        logger.info(f"💳 Создан платёж {payment.id} на {amount} {currency}")
        return {
            "payment_id": payment.id,
            "payment_url": payment.confirmation.confirmation_url,
        }
    except Exception as e:
        logger.error(f"❌ Ошибка создания платежа: {e}", exc_info=True)
        raise
