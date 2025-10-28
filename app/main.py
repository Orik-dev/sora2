from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.bot.init import bot, redis_pool
from app.core.db import engine
from app.core.logger import logger
from app.core.settings import settings
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.api.routers.telegram import router as telegram_router
from app.api.routers.yookassa import router as yookassa_router
from app.api.routers.sora import router as sora_router

# ALLOWED_UPDATES = ["message", "edited_message", "callback_query"]
ALLOWED_UPDATES = [
    "message", 
    "edited_message", 
    "callback_query",
    "pre_checkout_query", 
    "successful_payment",
]

def _build_webhook_url() -> str:
    return f"{settings.webhook_base()}/webhook/telegram"

def _assert_https(url: str) -> None:
    if not url.startswith("https://"):
        raise RuntimeError("WEBHOOK_DOMAIN must be HTTPS.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("📦 Lifespan start")

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        logger.info("✅ DB connected")

    url = _build_webhook_url()
    _assert_https(url)
    await bot.set_webhook(
        url=url,
        secret_token=settings.WEBHOOK_SECRET,
        drop_pending_updates=True,
        allowed_updates=ALLOWED_UPDATES,
        max_connections=50,
    )
    logger.info(f"📡 Telegram webhook set: {url}")

    if redis_pool:
        await redis_pool.ping()
        logger.info("✅ Redis connected")

    yield

    logger.info("🧹 shutdown")
    try: await bot.delete_webhook(drop_pending_updates=False)
    except Exception as e: logger.warning(f"delete_webhook: {e}")
    try: await bot.session.close()
    except Exception as e: logger.warning(f"bot.session.close: {e}")
    try:
        if redis_pool: await redis_pool.aclose()
    except Exception as e: logger.warning(f"redis close: {e}")

app = FastAPI(title="Sora2 Bot", lifespan=lifespan)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.WEBHOOK_DOMAIN],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(telegram_router, prefix="/webhook")
app.include_router(yookassa_router, prefix="/webhook")
app.include_router(sora_router,     prefix="/webhook")
