from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.logger import logger

class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Пытаемся определить язык из заголовков, иначе "ru"
        lang = request.headers.get("X-User-Lang") or "ru"
        request.state.lang = lang if lang in ("ru", "en") else "ru"
        return await call_next(request)
