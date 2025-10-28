# app/core/logger.py
import logging
import sys
from app.middleware.request_id import get_request_id

LOG_FORMAT = (
    '{"level":"%(levelname)s","msg":"%(message)s",'
    '"logger":"%(name)s","time":"%(asctime)s","module":"%(module)s",'
    '"line":%(lineno)d,"request_id":"%(request_id)s"}'
)

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # добавляем поле в каждый лог
        record.request_id = get_request_id()
        return True

def _setup() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]
    return logging.getLogger("Sora 2")

logger = _setup()
