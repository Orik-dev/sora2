from __future__ import annotations
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.logger import logger
from app.core.settings import settings
from app.models.models import VideoRequest, User
from app.domain.users.service import deduct_credits_atomic, get_or_create_user
from app.domain.generation.clients.sora import (
    submit_text_to_video, submit_image_to_video, SoraClientError
)
from app.domain.generation.exceptions import GenerationError

def _cost_for_duration(seconds: int) -> int:
    mapping = getattr(settings, "COST_PER_DURATION", {}) or {}
    # ключи могут прийти строками из .env — нормализуем
    if isinstance(mapping, dict) and isinstance(next(iter(mapping.keys()), 10), str):
        try:
            return int(mapping.get(str(seconds), 1))
        except Exception:
            return 1
    return int(mapping.get(seconds, 1))

async def start_generation(
    *,
    session: AsyncSession,
    telegram_id: int,
    prompt: str,
    model: str,                 # "sora2-t2v" | "sora2-i2v"
    aspect_ratio: str,          # "9:16" | "16:9"
    images_list: Optional[List[str]] = None,  # по MUAPI
) -> str:
    cost = int(settings.GENERATION_COST) 

    user = await get_or_create_user(session, telegram_id)
    ok = await deduct_credits_atomic(session, telegram_id, cost)
    if not ok:
        raise GenerationError("NO_CREDITS", user_message="❌ Недостаточно генераций.")

    vr = VideoRequest(
        user_id=telegram_id,
        chat_id=telegram_id,
        prompt=prompt,
        format=aspect_ratio,
        model=model,
        cost=cost,
        resolution="720P",
        status="pending",
    )
    session.add(vr)
    await session.commit()
    await session.refresh(vr)

    try:
        if model == "sora2-i2v":
            if not images_list:
                raise GenerationError("NO_IMAGE", user_message="❌ Требуется изображение.")
            task_id = await submit_image_to_video(
                prompt=prompt,
                images_list=images_list,
                aspect_ratio=aspect_ratio,
            )
        else:
            task_id = await submit_text_to_video(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )
    except (SoraClientError, GenerationError) as e:
        # откат списания
        await session.execute(
            update(User).where(User.user_id == telegram_id).values(credits=User.credits + cost)
        )
        await session.commit()
        logger.exception(f"[Sora2] submit failed: {e}")
        raise GenerationError("SUBMIT_FAILED", user_message="❌ Ошибка генерации. Попробуйте позже.")

    await session.execute(
        update(VideoRequest)
        .where(VideoRequest.id == vr.id)
        .values(task_id=task_id, status="processing")
    )
    await session.commit()
    logger.info(f"[Sora2] task created: request_id={task_id} vr_id={vr.id}")
    return task_id

async def save_result_by_request_id(
    session: AsyncSession,
    request_id: str,
    *,
    status: str,
    url: Optional[str],
    error: Optional[str],
) -> None:
    q = await session.execute(select(VideoRequest).where(VideoRequest.task_id == request_id))
    vr = q.scalars().first()
    if not vr:
        logger.warning(f"[Sora2] save_result: task not found {request_id}")
        return
    values = {"status": status}
    if url:
        values["video_url"] = url
    await session.execute(
        update(VideoRequest).where(VideoRequest.id == vr.id).values(**values)
    )
    await session.commit()
