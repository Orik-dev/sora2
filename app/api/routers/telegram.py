from fastapi import APIRouter, Request, Response, HTTPException
from aiogram.types import Update
from app.bot.init import bot, dp, redis_pool
from app.core.settings import settings
from app.core.logger import logger

router = APIRouter()

def _dedupe_key(update_id: int) -> str:
    return f"tg:update:{update_id}"

@router.post("/telegram")
async def telegram_webhook(request: Request):
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if token != settings.WEBHOOK_SECRET:
        logger.warning("Webhook: invalid secret token")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    data = await request.json()
    update = Update.model_validate(data)

    if update.update_id is not None and redis_pool is not None:
        key = _dedupe_key(update.update_id)
        added = await redis_pool.setnx(key, "1")
        if not added:
            return Response(status_code=204)
        await redis_pool.expire(key, 120)

    try:
        await dp.feed_update(bot, update)
    except Exception:
        logger.exception("Webhook: update processing failed")
        raise

    return Response(status_code=204)
