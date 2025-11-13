# from __future__ import annotations

# import asyncio
# import contextlib
# from typing import Any

# from sqlalchemy import select, update, delete
# from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest

# from app.bot.init import bot
# from app.core.db import SessionLocal
# from app.models.models import BroadcastJob, User
# from app.workers.rate import RateLimiter

# async def broadcast_send(ctx: dict[str, Any], job_id: str):
#     from app.core.settings import settings

#     rps = getattr(settings, "BROADCAST_RPS", 25)
#     concurrency = getattr(settings, "BROADCAST_CONCURRENCY", 20)
#     batch_size = getattr(settings, "BROADCAST_BATCH", 1000)

#     limiter = RateLimiter(rps=int(rps), concurrency=int(concurrency))
#     await limiter.start()

#     async with SessionLocal() as session:
#         row = await session.execute(select(BroadcastJob).where(BroadcastJob.id == job_id))
#         bj = row.scalars().first()
#         if not bj or bj.status in ("done", "cancelled"):
#             await limiter.stop()
#             return

#         await session.execute(update(BroadcastJob).where(BroadcastJob.id == job_id).values(status="running"))
#         await session.commit()

#         sent = 0
#         failed = 0
#         last_user_id = 0

#         async def _send(uid: int, text: str) -> bool:
#             slot = await limiter.ticket()
#             async with slot:
#                 try:
#                     await bot.send_message(uid, text)
#                     return True
#                 except TelegramRetryAfter as e:
#                     await asyncio.sleep(e.retry_after)
#                     try:
#                         await bot.send_message(uid, text)
#                         return True
#                     except (TelegramForbiddenError, TelegramBadRequest):
#                         async with SessionLocal() as s2:
#                             with contextlib.suppress(Exception):
#                                 await s2.execute(delete(User).where(User.user_id == uid))
#                                 await s2.commit()
#                         return False
#                     except Exception:
#                         return False
#                 except (TelegramForbiddenError, TelegramBadRequest):
#                     async with SessionLocal() as s2:
#                         with contextlib.suppress(Exception):
#                             await s2.execute(delete(User).where(User.user_id == uid))
#                             await s2.commit()
#                     return False
#                 except Exception:
#                     return False

#         while True:
#             st_row = await session.execute(select(BroadcastJob.status).where(BroadcastJob.id == job_id))
#             if (st := st_row.scalar_one_or_none()) == "cancelled":
#                 await session.execute(
#                     update(BroadcastJob).where(BroadcastJob.id == job_id).values(status="cancelled", note="Cancelled")
#                 )
#                 await session.commit()
#                 break

#             res = await session.execute(
#                 select(User.user_id)
#                 .where(User.user_id > last_user_id)
#                 .order_by(User.user_id)
#                 .limit(batch_size)
#             )
#             uids = res.scalars().all()
#             if not uids:
#                 await session.execute(
#                     update(BroadcastJob)
#                     .where(BroadcastJob.id == job_id)
#                     .values(status="done", note="Finished", sent=sent, failed=failed)
#                 )
#                 await session.commit()
#                 break

#             results = await asyncio.gather(*(_send(uid, bj.text) for uid in uids))
#             sent += sum(1 for ok in results if ok)
#             failed += sum(1 for ok in results if not ok)
#             await session.execute(
#                 update(BroadcastJob).where(BroadcastJob.id == job_id).values(sent=sent, failed=failed)
#             )
#             await session.commit()
#             last_user_id = uids[-1]

#     await limiter.stop()


from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from sqlalchemy import select, update, delete
from aiogram.exceptions import (
    TelegramRetryAfter,
    TelegramForbiddenError,
    TelegramBadRequest
)

from app.bot.init import bot
from app.core.db import SessionLocal
from app.core.settings import settings
from app.core.logger import logger
from app.models.models import BroadcastJob, User
from app.workers.rate import RateLimiter


async def broadcast_send(ctx: dict[str, Any], job_id: str):
    """
    Production-ready рассылка с:
    - Адаптивным rate limiting
    - Fallback на текст при ошибках с медиа
    - Удалением заблокировавших пользователей
    - HTML форматированием
    """
    rps = int(getattr(settings, "BROADCAST_RPS", 25))
    concurrency = int(getattr(settings, "BROADCAST_CONCURRENCY", 20))
    batch_size = int(getattr(settings, "BROADCAST_BATCH", 1000))
    check_cancel_every = 10

    limiter = RateLimiter(rps=rps, concurrency=concurrency)
    await limiter.start()

    async with SessionLocal() as session:
        # Получаем задачу
        row = await session.execute(
            select(BroadcastJob).where(BroadcastJob.id == job_id)
        )
        bj = row.scalars().first()
        
        if not bj or bj.status in ("done", "cancelled"):
            await limiter.stop()
            logger.info(f"[Broadcast] Job {job_id} already finished")
            return

        # Устанавливаем статус running
        await session.execute(
            update(BroadcastJob)
            .where(BroadcastJob.id == job_id)
            .values(status="running")
        )
        await session.commit()

        sent = 0
        failed = 0
        fallback = 0
        cancelled = False

        async def _send(uid: int, text: str, media_type: str | None, 
                       media_file_id: str | None) -> str:
            """
            Отправка с retry и fallback.
            Возвращает: 'success', 'fallback', 'failed'
            """
            async with limiter.ticket():
                for attempt in range(3):
                    try:
                        # ✅ Попытка отправить с медиа (ЧЕРЕЗ FILE_ID)
                        if media_type == "photo" and media_file_id:
                            await bot.send_photo(
                                uid,
                                photo=media_file_id,  # ✅ Используем file_id напрямую
                                caption=text,
                                parse_mode="HTML",  # ✅ HTML форматирование
                                request_timeout=45
                            )
                        elif media_type == "video" and media_file_id:
                            await bot.send_video(
                                uid,
                                video=media_file_id,  # ✅ Используем file_id напрямую
                                caption=text,
                                parse_mode="HTML",  # ✅ HTML форматирование
                                request_timeout=180
                            )
                        else:
                            # ✅ Текстовое сообщение
                            await bot.send_message(
                                uid,
                                text,
                                parse_mode="HTML",  # ✅ HTML форматирование
                                request_timeout=15
                            )
                        
                        return "success"
                    
                    except TelegramBadRequest as e:
                        error_msg = str(e).lower()
                        
                        # Обработка rate limit
                        if "too many requests" in error_msg or "retry after" in error_msg:
                            import re
                            match = re.search(r'retry after (\d+)', error_msg)
                            wait_time = int(match.group(1)) if match else 10
                            
                            if attempt < 2:
                                logger.debug(f"⏳ Rate limit for {uid}, waiting {wait_time}s")
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                # ✅ Последняя попытка — fallback на текст С HTML
                                try:
                                    await bot.send_message(
                                        uid,
                                        text,
                                        parse_mode="HTML",  # ✅ HTML форматирование
                                        request_timeout=15
                                    )
                                    return "fallback"
                                except Exception:
                                    return "failed"
                        
                        # Другие BadRequest ошибки → fallback
                        if attempt == 2:
                            logger.warning(f"⚠️ BadRequest for {uid}: {e}")
                            try:
                                # ✅ Fallback на текст С HTML
                                await bot.send_message(
                                    uid,
                                    text,
                                    parse_mode="HTML",  # ✅ HTML форматирование
                                    request_timeout=15
                                )
                                return "fallback"
                            except Exception:
                                pass
                            
                            # Удаляем пользователя
                            try:
                                async with SessionLocal() as s2:
                                    await s2.execute(
                                        delete(User).where(User.user_id == uid)
                                    )
                                    await s2.commit()
                            except Exception:
                                pass
                            return "failed"
                    
                    except TelegramForbiddenError:
                        # Пользователь заблокировал бота
                        try:
                            async with SessionLocal() as s2:
                                await s2.execute(
                                    delete(User).where(User.user_id == uid)
                                )
                                await s2.commit()
                        except Exception:
                            pass
                        return "failed"
                    
                    except TelegramRetryAfter as e:
                        if attempt < 2:
                            await asyncio.sleep(e.retry_after)
                            continue
                        return "failed"
                    
                    except Exception as e:
                        # Timeout или другие ошибки
                        if "timeout" in str(e).lower() and attempt < 2:
                            logger.warning(f"⏳ Timeout for {uid}, retry {attempt + 1}/3")
                            await asyncio.sleep(5)
                            continue
                        
                        logger.error(f"❌ Unexpected error for {uid}: {e}")
                        return "failed"
                
                return "failed"

        # Основной цикл рассылки
        last_user_id = 0
        total_processed = 0
        
        while not cancelled:
            # Проверка отмены ПЕРЕД каждым батчем
            st_row = await session.execute(
                select(BroadcastJob.status).where(BroadcastJob.id == job_id)
            )
            status = st_row.scalar_one_or_none()
            
            if status == "cancelled":
                cancelled = True
                logger.warning(f"🛑 Broadcast {job_id} cancelled")
                break

            # Получаем батч пользователей
            try:
                res = await session.execute(
                    select(User.user_id)
                    .where(User.user_id > last_user_id)
                    .order_by(User.user_id)
                    .limit(batch_size)
                )
                user_ids = res.scalars().all()
            except Exception as e:
                logger.error(f"❌ Failed to fetch users: {e}")
                await session.execute(
                    update(BroadcastJob)
                    .where(BroadcastJob.id == job_id)
                    .values(
                        status="error",
                        sent=sent,
                        failed=failed,
                        fallback=fallback,
                        note=f"DB error: {e}"
                    )
                )
                await session.commit()
                break
            
            # Завершение рассылки
            if not user_ids:
                logger.info(
                    f"✅ Broadcast {job_id} complete: "
                    f"sent={sent}, fallback={fallback}, failed={failed}"
                )
                break

            # Отправка с проверкой отмены каждые N сообщений
            for i in range(0, len(user_ids), check_cancel_every):
                if cancelled:
                    break
                
                # Проверка статуса внутри батча
                if i > 0:
                    st_row = await session.execute(
                        select(BroadcastJob.status).where(BroadcastJob.id == job_id)
                    )
                    if st_row.scalar_one_or_none() == "cancelled":
                        cancelled = True
                        logger.warning(f"🛑 Broadcast {job_id} cancelled during batch")
                        break
                
                # Отправка чанка
                chunk = user_ids[i:i + check_cancel_every]
                tasks = [
                    asyncio.create_task(
                        _send(uid, bj.text, bj.media_type, bj.media_file_id)
                    )
                    for uid in chunk
                ]
                results = await asyncio.gather(*tasks)
                
                # Подсчет результатов
                sent += sum(1 for r in results if r == "success")
                failed += sum(1 for r in results if r == "failed")
                fallback += sum(1 for r in results if r == "fallback")
                total_processed += len(results)
            
            # Сохранение прогресса после батча
            await session.execute(
                update(BroadcastJob)
                .where(BroadcastJob.id == job_id)
                .values(
                    sent=sent,
                    failed=failed,
                    fallback=fallback,
                    note=f"Progress: {total_processed}/{bj.total}. Fallback: {fallback}"
                )
            )
            await session.commit()
            
            last_user_id = user_ids[-1]

        # Остановка rate limiter
        await limiter.stop()
        
        # Финальное обновление
        final_status = "cancelled" if cancelled else "done"
        final_note = f"{'Cancelled' if cancelled else 'Completed'}. Fallback: {fallback}"
        
        await session.execute(
            update(BroadcastJob)
            .where(BroadcastJob.id == job_id)
            .values(
                status=final_status,
                sent=sent,
                failed=failed,
                fallback=fallback,
                note=final_note
            )
        )
        await session.commit()
        
        # Уведомление админу
        if settings.ADMIN_ID and not cancelled:
            try:
                total = sent + failed + fallback
                success_rate = (sent / total * 100) if total > 0 else 0
                fallback_rate = (fallback / total * 100) if total > 0 else 0
                failed_rate = (failed / total * 100) if total > 0 else 0
                
                media_info = ""
                if bj.media_type == "photo":
                    media_info = " (📸 фото)"
                elif bj.media_type == "video":
                    media_info = " (🎬 видео)"
                
                await bot.send_message(
                    settings.ADMIN_ID,
                    f"📣 Рассылка <code>#{job_id}</code>{media_info} завершена\n\n"
                    f"📊 Статистика:\n"
                    f"├ Всего: <b>{total}</b>\n"
                    f"├ ✅ Медиа: <b>{sent}</b> ({success_rate:.1f}%)\n"
                    f"├ ⚠️ Текст: <b>{fallback}</b> ({fallback_rate:.1f}%)\n"
                    f"└ ❌ Ошибки: <b>{failed}</b> ({failed_rate:.1f}%)",
                    parse_mode="HTML"  # ✅ HTML форматирование
                )
            except Exception as e:
                logger.exception(f"Failed to send admin notification: {e}")