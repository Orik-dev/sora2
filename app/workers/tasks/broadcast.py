from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from sqlalchemy import select, update, delete
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest

from app.bot.init import bot
from app.core.db import SessionLocal
from app.models.models import BroadcastJob, User
from app.workers.rate import RateLimiter

async def broadcast_send(ctx: dict[str, Any], job_id: str):
    from app.core.settings import settings

    rps = getattr(settings, "BROADCAST_RPS", 25)
    concurrency = getattr(settings, "BROADCAST_CONCURRENCY", 20)
    batch_size = getattr(settings, "BROADCAST_BATCH", 1000)

    limiter = RateLimiter(rps=int(rps), concurrency=int(concurrency))
    await limiter.start()

    async with SessionLocal() as session:
        row = await session.execute(select(BroadcastJob).where(BroadcastJob.id == job_id))
        bj = row.scalars().first()
        if not bj or bj.status in ("done", "cancelled"):
            await limiter.stop()
            return

        await session.execute(update(BroadcastJob).where(BroadcastJob.id == job_id).values(status="running"))
        await session.commit()

        sent = 0
        failed = 0
        last_user_id = 0

        async def _send(uid: int, text: str) -> bool:
            slot = await limiter.ticket()
            async with slot:
                try:
                    await bot.send_message(uid, text)
                    return True
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    try:
                        await bot.send_message(uid, text)
                        return True
                    except (TelegramForbiddenError, TelegramBadRequest):
                        async with SessionLocal() as s2:
                            with contextlib.suppress(Exception):
                                await s2.execute(delete(User).where(User.user_id == uid))
                                await s2.commit()
                        return False
                    except Exception:
                        return False
                except (TelegramForbiddenError, TelegramBadRequest):
                    async with SessionLocal() as s2:
                        with contextlib.suppress(Exception):
                            await s2.execute(delete(User).where(User.user_id == uid))
                            await s2.commit()
                    return False
                except Exception:
                    return False

        while True:
            st_row = await session.execute(select(BroadcastJob.status).where(BroadcastJob.id == job_id))
            if (st := st_row.scalar_one_or_none()) == "cancelled":
                await session.execute(
                    update(BroadcastJob).where(BroadcastJob.id == job_id).values(status="cancelled", note="Cancelled")
                )
                await session.commit()
                break

            res = await session.execute(
                select(User.user_id)
                .where(User.user_id > last_user_id)
                .order_by(User.user_id)
                .limit(batch_size)
            )
            uids = res.scalars().all()
            if not uids:
                await session.execute(
                    update(BroadcastJob)
                    .where(BroadcastJob.id == job_id)
                    .values(status="done", note="Finished", sent=sent, failed=failed)
                )
                await session.commit()
                break

            results = await asyncio.gather(*(_send(uid, bj.text) for uid in uids))
            sent += sum(1 for ok in results if ok)
            failed += sum(1 for ok in results if not ok)
            await session.execute(
                update(BroadcastJob).where(BroadcastJob.id == job_id).values(sent=sent, failed=failed)
            )
            await session.commit()
            last_user_id = uids[-1]

    await limiter.stop()
