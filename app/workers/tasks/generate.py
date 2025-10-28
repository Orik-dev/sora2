# from __future__ import annotations
# from typing import Optional

# from sqlalchemy import select, update
# from app.core.db import SessionLocal
# from app.core.settings import settings
# from app.core.logger import logger
# from app.models.models import User, VideoRequest
# from app.workers.helpers import send_text
# from app.domain.generation.clients.sora import create_text_video, create_image_video

# async def queue_generation(
#     ctx: dict,
#     *,
#     telegram_id: int,
#     prompt: str,
#     model: str,          # "sora2-t2v" | "sora2-i2v"
#     aspect_ratio: str,   # "9:16" | "16:9"
#     images_list: Optional[list[str]],
# ):
#     """
#     1) Проверяем, что у пользователя ХВАТИТ кредитов (без списания).
#     2) Создаём VideoRequest(pending).
#     3) Вызываем OpenAI Videos API (официальный).
#     4) Сохраняем video.id в task_id и ставим status=processing.
#     Списание делаем ТОЛЬКО в вебхуке по video.completed → отправили видео → списали.
#     """
#     cost = int(getattr(settings, "GENERATION_COST", 1) or 1)

#     async with SessionLocal() as session:
#         row = await session.execute(select(User).where(User.user_id == telegram_id))
#         user = row.scalars().first()
#         if not user or (user.credits or 0) < cost:
#             await send_text(telegram_id, "❌ Недостаточно генераций. Пополните баланс.")
#             return

#         vr = VideoRequest(
#             user_id=telegram_id,
#             chat_id=telegram_id,
#             prompt=prompt,
#             format=aspect_ratio,
#             model=model,
#             cost=cost,
#             duration=10,
#             resolution="720P",
#             status="pending",
#         )
#         session.add(vr)
#         await session.commit()
#         await session.refresh(vr)

#         try:
#             if model == "sora2-i2v" and images_list:
#                 # берём первое изображение как reference
#                 video_id = await create_image_video(prompt=prompt, image_url=images_list[0], aspect_ratio=aspect_ratio)
#             else:
#                 video_id = await create_text_video(prompt=prompt, aspect_ratio=aspect_ratio)
#         except Exception as e:
#             await session.execute(update(VideoRequest).where(VideoRequest.id == vr.id).values(status="failed"))
#             await session.commit()
#             logger.exception(f"[Sora] submit failed: {e}")
#             await send_text(telegram_id, "❌ Ошибка генерации. Попробуйте переформулировать запрос или позже.")
#             return

#         await session.execute(
#             update(VideoRequest).where(VideoRequest.id == vr.id).values(task_id=video_id, status="processing")
#         )
#         await session.commit()


# app/workers/tasks/generate.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy import select, update
from app.core.db import SessionLocal
from app.core.settings import settings
from app.core.logger import logger
from app.models.models import User, VideoRequest
from app.workers.helpers import send_text
from app.domain.generation.clients.sora import (
    submit_text_to_video,
    submit_image_to_video,
)

async def queue_generation(
    ctx: dict,
    *,
    telegram_id: int,
    prompt: str,
    model: str,          # "sora2-t2v" | "sora2-i2v"
    aspect_ratio: str,   # "9:16" | "16:9"
    images_list: Optional[List[str]] = None,
):
    """
    1) Проверяем баланс (без списания).
    2) Создаём VideoRequest(pending).
    3) Submit to Kie AI (возвращает taskId).
    4) Сохраняем task_id, status=processing.
    Списание в callback webhook после отправки.
    """
    cost = int(getattr(settings, "GENERATION_COST", 1) or 1)

    async with SessionLocal() as session:
        row = await session.execute(select(User).where(User.user_id == telegram_id))
        user = row.scalars().first()
        if not user or (user.credits or 0) < cost:
            await send_text(telegram_id, "❌ Недостаточно генераций. Пополните баланс.")
            return

        vr = VideoRequest(
            user_id=telegram_id,
            chat_id=telegram_id,
            prompt=prompt,
            format=aspect_ratio,
            model=model,
            cost=cost,
            duration=10,
            resolution="720P",
            status="pending",
        )
        session.add(vr)
        await session.commit()
        await session.refresh(vr)

        task_id = None
        try:
            if model == "sora2-i2v" and images_list:
                task_id = await submit_image_to_video(
                    prompt=prompt,
                    image_urls=images_list,
                    aspect_ratio=aspect_ratio,
                )
            else:
                task_id = await submit_text_to_video(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                )
        except Exception as e:
            await session.execute(update(VideoRequest).where(VideoRequest.id == vr.id).values(status="failed"))
            await session.commit()
            logger.exception(f"[Sora] submit failed: {e}")
            await send_text(telegram_id, "❌ Ошибка генерации. Попробуйте переформулировать запрос или позже.")
            return

        await session.execute(
            update(VideoRequest)
            .where(VideoRequest.id == vr.id)
            .values(task_id=task_id, status="processing")
        )
        await session.commit()

        logger.info(f"[Sora] task enqueued: task_id={task_id} vr_id={vr.id}")