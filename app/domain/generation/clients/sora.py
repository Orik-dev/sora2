# # app/domain/generation/clients/sora.py
# from __future__ import annotations
# import aiohttp
# import json
# from typing import List
# from app.core.settings import settings
# from app.core.logger import logger
# from app.domain.generation.exceptions import GenerationError

# async def _submit_task(model: str, input_data: dict) -> str:
#     payload = {
#         "model": model,
#         "input": input_data,
#         "callBackUrl": f"{settings.webhook_base()}/webhook/sora"
#     }
#     headers = {
#         "Authorization": f"Bearer {settings.KIE_API_KEY}",
#         "Content-Type": "application/json"
#     }
#     async with aiohttp.ClientSession() as session:
#         async with session.post(
#             f"{settings.KIE_BASE_URL}/jobs/createTask",
#             json=payload,
#             headers=headers
#         ) as resp:
#             if resp.status != 200:
#                 try:
#                     error_text = await resp.text()
#                     error_data = json.loads(error_text) if error_text else {}
#                     msg = error_data.get("msg", f"HTTP {resp.status}")
#                     code_map = {
#                         400: "Invalid request parameters",
#                         401: "Authentication failed",
#                         402: "Insufficient balance",
#                         404: "Resource not found",
#                         422: "Parameter validation failed",
#                         429: "Rate limit exceeded",
#                         500: "Internal server error"
#                     }
#                     user_msg = code_map.get(resp.status, "Unknown error")
#                 except:
#                     user_msg = "Request failed"
#                     msg = str(resp.status)
#                 raise GenerationError(
#                     f"KIE_{resp.status}",
#                     user_message=f"❌ {user_msg}",
#                     technical=msg
#                 )
#             data = await resp.json()
#             if data.get("code") != 200:
#                 raise GenerationError(
#                     f"KIE_{data.get('code', 'UNKNOWN')}",
#                     user_message="❌ API error",
#                     technical=data.get("msg", "Unknown")
#                 )
#             task_id = data["data"]["taskId"]
#             logger.info(f"[Kie Sora] task created: {task_id}")
#             return task_id

# def _ar_mapping(ar: str) -> str:
#     return "portrait" if ar == "9:16" else "landscape"

# async def submit_text_to_video(prompt: str, aspect_ratio: str) -> str:
#     ar = _ar_mapping(aspect_ratio)
#     input_data = {
#         "prompt": prompt,
#         "aspect_ratio": ar
#     }
#     return await _submit_task("sora-2-text-to-video", input_data)

# async def submit_image_to_video(prompt: str, image_urls: List[str], aspect_ratio: str) -> str:
#     ar = _ar_mapping(aspect_ratio)
#     input_data = {
#         "prompt": prompt,
#         "image_urls": image_urls,
#         "aspect_ratio": ar
#     }
#     return await _submit_task("sora-2-image-to-video", input_data)

from __future__ import annotations
import aiohttp
import json
from typing import List, Optional
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

def _ar_mapping(ar: Optional[str]) -> Optional[str]:
    """
    Преобразует aspect_ratio в формат API.
    Если None - API сам определит из загруженного изображения.
    """
    if ar is None:
        return None
    return "portrait" if ar == "9:16" else "landscape"

async def submit_text_to_video(prompt: str, aspect_ratio: str) -> str:
    ar = _ar_mapping(aspect_ratio)
    input_data = {
        "prompt": prompt,
        "aspect_ratio": ar
    }
    return await _submit_task("sora-2-text-to-video", input_data)

async def submit_image_to_video(prompt: str, image_urls: List[str], aspect_ratio: Optional[str]) -> str:
    """
    aspect_ratio может быть None - тогда API использует размер оригинального изображения
    """
    input_data = {
        "prompt": prompt,
        "image_urls": image_urls
    }
    
    # ✅ Добавляем aspect_ratio только если он задан
    ar = _ar_mapping(aspect_ratio)
    if ar is not None:
        input_data["aspect_ratio"] = ar
    
    return await _submit_task("sora-2-image-to-video", input_data)