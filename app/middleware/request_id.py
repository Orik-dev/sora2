# app/middleware/request_id.py
import uuid
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

def get_request_id() -> str:
    return _request_id_ctx.get()

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        _request_id_ctx.set(rid)
        # прокидываем в response
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
