from __future__ import annotations

class GenerationError(Exception):
    def __init__(self, code: str, *, user_message: str | None = None, technical: str | None = None, http_status: int | None = None):
        super().__init__(technical or user_message or code)
        self.code = code
        self.user_message = user_message or "Сервис вернул ошибку. Попробуйте снова."
        self.technical = technical
        self.http_status = http_status
