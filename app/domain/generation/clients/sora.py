# from __future__ import annotations
# import asyncio
# import tempfile
# from typing import Optional
# import aiohttp

# from openai import AsyncOpenAI
# from app.core.settings import settings
# from app.core.logger import logger

# client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# # утилита: подбирать size по AR (720p)
# def _size_for_ar(ar: str) -> str:
#     return "720x1280" if ar == "9:16" else "1280x720"

# async def create_text_video(*, prompt: str, aspect_ratio: str, seconds: int = 12) -> str:
#     """
#     Возвращает ID рендера (video.id). Webhook уведомит по завершении.
#     """
#     size = _size_for_ar(aspect_ratio)
#     logger.info(f"[Sora] create T2V: size={size}, seconds={seconds}")
#     video = await client.videos.create(
#         model=settings.SORA_DEFAULT_MODEL,
#         prompt=prompt,
#         size=size,
#         seconds=str(int(seconds)),
#     )
#     logger.info(f"[Sora] created video id={video.id} status={video.status}")
#     return video.id

# async def _download_to_temp(url: str) -> str:
#     """
#     Скачивает URL (tg file) в temp-файл для input_reference.
#     """
#     async with aiohttp.ClientSession() as s:
#         async with s.get(url) as r:
#             r.raise_for_status()
#             fd, path = tempfile.mkstemp(suffix=".jpg")
#             with open(fd, "wb") as f:
#                 f.write(await r.read())
#             return path

# async def create_image_video(
#     *, prompt: str, image_url: str, aspect_ratio: str, seconds: int = 10
# ) -> str:
#     """
#     image_url — публичный URL фото из TG.
#     Важно: размер исходной картинки должен совпадать с target size (см. доку),
#     иначе API может отклонить. Мы не ресайзим, просто отправляем как есть.
#     """
#     size = _size_for_ar(aspect_ratio)
#     logger.info(f"[Sora] create I2V: size={size}, seconds={seconds}")
#     tmp_path = await _download_to_temp(image_url)
#     try:
#         with open(tmp_path, "rb") as ref:
#             video = await client.videos.create(
#                 model=settings.SORA_DEFAULT_MODEL,
#                 prompt=prompt,
#                 size=size,
#                 seconds=str(int(seconds)),
#                 input_reference=ref,  # офиц. поле для стартового кадра
#             )
#         logger.info(f"[Sora] created video id={video.id} status={video.status}")
#         return video.id
#     finally:
#         try:
#             import os; os.remove(tmp_path)
#         except Exception:
#             pass

# async def retrieve(video_id: str):
#     return await client.videos.retrieve(video_id)

# async def download_mp4(video_id: str, *, to_path: Optional[str] = None) -> str:
#     """
#     Скачивает готовый MP4 (variant=video) в локальный файл и возвращает путь.
#     """
#     content = await client.videos.download_content(video_id, variant="video")
#     out = to_path or tempfile.mktemp(suffix=".mp4")
#     content.write_to_file(out)
#     return out


# app/domain/generation/clients/sora.py
from __future__ import annotations
import aiohttp
import json
from typing import List
from app.core.settings import settings
from app.core.logger import logger
from app.domain.generation.exceptions import GenerationError

async def _submit_task(model: str, input_data: dict) -> str:
    payload = {
        "model": model,
        "input": input_data,
        "callBackUrl": f"{settings.webhook_base()}/webhook/sora"
    }
    headers = {
        "Authorization": f"Bearer {settings.KIE_API_KEY}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{settings.KIE_BASE_URL}/jobs/createTask",
            json=payload,
            headers=headers
        ) as resp:
            if resp.status != 200:
                try:
                    error_text = await resp.text()
                    error_data = json.loads(error_text) if error_text else {}
                    msg = error_data.get("msg", f"HTTP {resp.status}")
                    code_map = {
                        400: "Invalid request parameters",
                        401: "Authentication failed",
                        402: "Insufficient balance",
                        404: "Resource not found",
                        422: "Parameter validation failed",
                        429: "Rate limit exceeded",
                        500: "Internal server error"
                    }
                    user_msg = code_map.get(resp.status, "Unknown error")
                except:
                    user_msg = "Request failed"
                    msg = str(resp.status)
                raise GenerationError(
                    f"KIE_{resp.status}",
                    user_message=f"❌ {user_msg}",
                    technical=msg
                )
            data = await resp.json()
            if data.get("code") != 200:
                raise GenerationError(
                    f"KIE_{data.get('code', 'UNKNOWN')}",
                    user_message="❌ API error",
                    technical=data.get("msg", "Unknown")
                )
            task_id = data["data"]["taskId"]
            logger.info(f"[Kie Sora] task created: {task_id}")
            return task_id

def _ar_mapping(ar: str) -> str:
    return "portrait" if ar == "9:16" else "landscape"

async def submit_text_to_video(prompt: str, aspect_ratio: str) -> str:
    ar = _ar_mapping(aspect_ratio)
    input_data = {
        "prompt": prompt,
        "aspect_ratio": ar
    }
    return await _submit_task("sora-2-text-to-video", input_data)

async def submit_image_to_video(prompt: str, image_urls: List[str], aspect_ratio: str) -> str:
    ar = _ar_mapping(aspect_ratio)
    input_data = {
        "prompt": prompt,
        "image_urls": image_urls,
        "aspect_ratio": ar
    }
    return await _submit_task("sora-2-image-to-video", input_data)