# app/bot/init.py
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from app.core.settings import settings
# from app.core.redis import make_redis_pool
from app.core.redis_pool import redis_pool
from app.bot.handlers.payments import register_payment_handlers
from app.bot.handlers.example import register_example_handlers
# from app.bot.handlers.invite import register_invite_handlers
from app.bot.handlers.bots import register_bots_handlers
from app.bot.handlers.broadcast import register_broadcast_handlers
bot = Bot(
    token=settings.TELEGRAM_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
# redis_pool = make_redis_pool()

# Стартовые хэндлеры
from app.bot.handlers.start import register_start_handlers

# Новые хэндлеры (Шаг 2)
from app.bot.handlers.text import register_text_handlers
from app.bot.handlers.image import register_image_handlers

register_text_handlers(dp)
register_image_handlers(dp)
register_payment_handlers(dp)
register_start_handlers(dp) 


register_example_handlers(dp)    # /example
# register_invite_handlers(dp)     # /invite_friend (+ автоначисление на /start)
register_bots_handlers(dp)       # /bots
register_broadcast_handlers(dp)  # /broadcast, /broadcast_cancel, /broadcast_status (только админ)
