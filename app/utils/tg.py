from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter, TelegramNetworkError, TelegramAPIError
from app.core.logger import logger
import asyncio

async def safe_cb_answer(cb, text: str | None = None, show_alert: bool = False) -> None:
    try:
        await cb.answer(text=text, show_alert=show_alert, cache_time=0)
    except TelegramBadRequest:
        logger.debug("safe_cb_answer: query is too old/invalid")
    except (TelegramAPIError, TelegramNetworkError):
        logger.debug("safe_cb_answer: api/network error ignored")
    except Exception as e:
        logger.warning(f"safe_cb_answer: unexpected error: {e}")

async def send_safe(send_coro_factory, *, retries: int = 2) -> bool:
    for attempt in range(retries + 1):
        try:
            await send_coro_factory()
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            # пользователь заблокировал/удалил бота — считаем, что отправка невозможна
            return False
        except TelegramBadRequest as e:
            # например, message is not modified / can't parse entities
            logger.debug(f"send_safe bad request: {e.message}")
            return False
        except (TelegramAPIError, TelegramNetworkError) as e:
            logger.debug(f"send_safe api/network: {e}")
            await asyncio.sleep(1 + attempt)
        except Exception as e:
            logger.warning(f"send_safe unexpected: {e}")
            await asyncio.sleep(1 + attempt)
    return False
