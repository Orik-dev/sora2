from __future__ import annotations
import asyncio
import contextlib
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramForbiddenError
from aiogram.types import FSInputFile
from app.bot.init import bot

async def send_video(chat_id: int, file_path_or_url: str, caption: str | None = None, *, timeout: int = 180) -> None:
    """
    Если передали локальный путь — загрузим файлом. Если URL — отправим как URL.
    """
    try:
        if file_path_or_url.startswith("http"):
            await bot.send_video(chat_id, video=file_path_or_url, caption=caption or "", request_timeout=timeout)
        else:
            await bot.send_video(chat_id, video=FSInputFile(file_path_or_url), caption=caption or "", request_timeout=timeout)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        with contextlib.suppress(Exception):
            if file_path_or_url.startswith("http"):
                await bot.send_video(chat_id, video=file_path_or_url, caption=caption or "", request_timeout=timeout)
            else:
                await bot.send_video(chat_id, video=FSInputFile(file_path_or_url), caption=caption or "", request_timeout=timeout)
    except (TelegramForbiddenError, TelegramBadRequest):
        pass

async def send_text(chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        with contextlib.suppress(Exception):
            await bot.send_message(chat_id, text)
    except (TelegramForbiddenError, TelegramBadRequest):
        pass
