# from __future__ import annotations
# import json
# import os
# from fastapi import APIRouter, Request, HTTPException, Depends
# from starlette.responses import Response
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, update

# from app.repo.db import get_session
# from app.core.settings import settings
# from app.core.logger import logger
# from app.models.models import VideoRequest, User
# from app.workers.helpers import send_video, send_text

# router = APIRouter()

# # Маппинг популярных ошибок на русский (расширенный)


# @router.post("/sora")
# async def sora_webhook(request: Request, session: AsyncSession = Depends(get_session)):
#     """
#     Callback от Kie AI Sora 2: POST JSON как в /recordInfo.
#     Обработка success/fail, отправка видео, списание.
#     """
#     try:
#         data = await request.json()
#     except Exception:
#         logger.warning("[Sora] webhook: invalid JSON")
#         raise HTTPException(400, "invalid JSON")

#     # Логгируем non-200, но НЕ возвращаем досрочно — продолжаем обработку
#     if data.get("code") != 200:
#         logger.warning(f"[Sora] webhook: non-200 code {data.get('code')}: {data}")

#     task_data = data.get("data", {})
#     task_id = task_data.get("taskId")
#     state = task_data.get("state")

#     logger.info(f"[Sora] webhook: task_id={task_id} state={state}")

#     if not task_id:
#         return Response(status_code=200)

#     # найдём нашу задачу по task_id
#     q = await session.execute(select(VideoRequest).where(VideoRequest.task_id == task_id))
#     vr = q.scalars().first()
#     if not vr:
#         logger.warning(f"[Sora] webhook: VideoRequest not found for {task_id}")
#         return Response(status_code=200)

#     if state == "fail":
#         fail_msg = task_data.get("failMsg", "Unknown error")
#         fail_code = task_data.get("failCode")
        
#         # Кастомное сообщение из маппинга (если не нашли — используем дефолт с переводом)
#         user_msg = ERROR_MAP.get(fail_msg, f"❌ Генерация отклонена ({fail_msg}). Попробуйте переформулировать промпт/изображение.")
        
#         logger.warning(f"[Sora] task failed: {task_id} code={fail_code} msg={fail_msg}")
#         await session.execute(update(VideoRequest).where(VideoRequest.id == vr.id).values(status="failed"))
#         await session.commit()
        
#         # Отправляем кастомное сообщение пользователю
#         await send_text(vr.chat_id, user_msg)
        
#         # Баланс не списывался (пока не success + send_video), так что refund не нужен.
#         # Если в будущем добавишь предсписание — раскомментируй:
#         # await session.execute(update(User).where(User.user_id == vr.user_id).values(credits=User.credits + (vr.cost or 1)))
#         # await session.commit()
        
#         return Response(status_code=200)

#     if state != "success":
#         return Response(status_code=200)

#     # success: извлекаем URL из resultJson
#     result_json_str = task_data.get("resultJson")
#     if not result_json_str:
#         logger.warning(f"[Sora] webhook: no resultJson for {task_id}")
#         return Response(status_code=200)

#     try:
#         results = json.loads(result_json_str)
#         video_url = results.get("resultUrls", [None])[0]
#         if not video_url:
#             raise ValueError("no resultUrls")
#     except Exception as e:
#         logger.exception(f"[Sora] webhook: invalid resultJson {result_json_str}: {e}")
#         return Response(status_code=200)

#     # пометим как completed
#     await session.execute(
#         update(VideoRequest)
#         .where(VideoRequest.id == vr.id)
#         .values(status="completed", video_url=video_url)
#     )
#     await session.commit()

#     # отправляем URL напрямую (public)
#     sent_ok = False
#     try:
#         await send_video(vr.chat_id, video_url, "✅ Готово! Вот ваше видео.")
#         sent_ok = True
#     except Exception as e:
#         logger.exception(f"[Sora] send_video failed: {e}")
#         sent_ok = False

#     # списываем только если отправили
#     if sent_ok:
#         res = await session.execute(
#             update(User)
#             .where(User.user_id == vr.user_id, User.credits >= (vr.cost or 1))
#             .values(credits=User.credits - (vr.cost or 1))
#         )
#         if res.rowcount == 0:
#             logger.warning(f"[Sora] not enough credits to deduct post-send user={vr.user_id} task={vr.id}")
#             await session.rollback()
#         else:
#             await session.commit()
#     else:
#         # refund если ранее списано (но у нас не списано ранее)
#         await session.execute(
#             update(User)
#             .where(User.user_id == vr.user_id)
#             .values(credits=User.credits + (vr.cost or 1))
#         )
#         await session.commit()

#     return Response(status_code=200)

from __future__ import annotations
import json
import os
from fastapi import APIRouter, Request, HTTPException, Depends
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.repo.db import get_session
from app.core.settings import settings
from app.core.logger import logger
from app.models.models import VideoRequest, User
from app.workers.helpers import send_video, send_text

router = APIRouter()

ERROR_MAP = {
    "We currently do not support uploads of images containing photorealistic people.": 
        "❌ Фото с реалистичными людьми не поддерживается (ограничение Sora 2). Используйте рисунки, анимации или схемы!",
    "This content may violate our guardrails concerning similarity to third-party content.": 
        "❌ Контент похож на чужую интеллектуальную собственность (логотипы, персонажи). Используйте оригинальные рисунки или абстрактные изображения!",
    "Invalid request parameters": 
        "❌ Неверные параметры. Упростите промпт (макс. 5000 символов).",
    "Parameter validation failed": 
        "❌ Ошибка валидации. Проверьте изображение (JPEG/PNG/WEBP, <10MB).",
    "Insufficient account balance": 
        "❌ Обратитесь к поддержке @guard_gpt.",
    # Добавляй новые по логам
}

# ERROR_MAP = {
#     "We currently do not support uploads of images containing photorealistic people.": 
#         "❌ Фото с реалистичными людьми не поддерживается (ограничение Sora 2).\n\n"
#         "Используйте рисунки, анимации или схемы, либо напишите в поддержку:\n"
#         "👉 @guard_gpt",
#     "This content may violate our guardrails concerning similarity to third-party content.": 
#         "❌ Контент похож на чужую интеллектуальную собственность.\n\n"
#         "Используйте оригинальные рисунки или напишите в поддержку:\n"
#         "👉 @guard_gpt",
#     "Invalid request parameters": 
#         "❌ Неверные параметры.\n\n"
#         "Упростите промпт (макс. 5000 символов) или напишите в поддержку:\n"
#         "👉 @guard_gpt",
#     "Parameter validation failed": 
#         "❌ Ошибка валидации.\n\n"
#         "Проверьте изображение (JPEG/PNG/WEBP, <10MB) или напишите в поддержку:\n"
#         "👉 @guard_gpt",
#     "Insufficient account balance": 
#         "❌Обратитесь в поддержку:\n"
#         "👉 @guard_gpt",
# }

@router.post("/sora")
async def sora_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    """
    Callback от Kie AI Sora 2: POST JSON.
    Обработка success/fail, отправка видео, списание.
    """
    try:
        data = await request.json()
    except Exception:
        logger.warning("[Sora] webhook: invalid JSON")
        raise HTTPException(400, "invalid JSON")

    if data.get("code") != 200:
        logger.warning(f"[Sora] webhook: non-200 code {data.get('code')}: {data}")

    task_data = data.get("data", {})
    task_id = task_data.get("taskId")
    state = task_data.get("state")

    logger.info(f"[Sora] webhook: task_id={task_id} state={state}")

    if not task_id:
        return Response(status_code=200)

    q = await session.execute(select(VideoRequest).where(VideoRequest.task_id == task_id))
    vr = q.scalars().first()
    if not vr:
        logger.warning(f"[Sora] webhook: VideoRequest not found for {task_id}")
        return Response(status_code=200)

    if state == "fail":
        fail_msg = task_data.get("failMsg", "Unknown error")
        fail_code = task_data.get("failCode")
        
        # Используем кастомное сообщение или дефолт с поддержкой
        user_msg = ERROR_MAP.get(
            fail_msg, 
            f"❌ Генерация отклонена: {fail_msg}\n\n"
            "Попробуйте переформулировать промпт/изображение или напишите в поддержку:\n"
            "👉 @guard_gpt"
        )
        
        logger.warning(f"[Sora] task failed: {task_id} code={fail_code} msg={fail_msg}")
        await session.execute(update(VideoRequest).where(VideoRequest.id == vr.id).values(status="failed"))
        await session.commit()
        
        await send_text(vr.chat_id, user_msg)
        
        return Response(status_code=200)

    if state != "success":
        return Response(status_code=200)

    # success: извлекаем URL
    result_json_str = task_data.get("resultJson")
    if not result_json_str:
        logger.warning(f"[Sora] webhook: no resultJson for {task_id}")
        return Response(status_code=200)

    try:
        results = json.loads(result_json_str)
        video_url = results.get("resultUrls", [None])[0]
        if not video_url:
            raise ValueError("no resultUrls")
    except Exception as e:
        logger.exception(f"[Sora] webhook: invalid resultJson {result_json_str}: {e}")
        return Response(status_code=200)

    await session.execute(
        update(VideoRequest)
        .where(VideoRequest.id == vr.id)
        .values(status="completed", video_url=video_url)
    )
    await session.commit()

    # отправляем видео
    sent_ok = False
    try:
        await send_video(vr.chat_id, video_url, "✅ Готово! Вот ваше видео.")
        sent_ok = True
    except Exception as e:
        logger.exception(f"[Sora] send_video failed: {e}")
        sent_ok = False

    # списываем только если отправили
    if sent_ok:
        res = await session.execute(
            update(User)
            .where(User.user_id == vr.user_id, User.credits >= (vr.cost or 1))
            .values(credits=User.credits - (vr.cost or 1))
        )
        if res.rowcount == 0:
            logger.warning(f"[Sora] not enough credits to deduct post-send user={vr.user_id} task={vr.id}")
            await session.rollback()
        else:
            await session.commit()
    else:
        await session.execute(
            update(User)
            .where(User.user_id == vr.user_id)
            .values(credits=User.credits + (vr.cost or 1))
        )
        await session.commit()

    return Response(status_code=200)