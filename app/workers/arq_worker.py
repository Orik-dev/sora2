from __future__ import annotations
import asyncio
from arq import run_worker, cron
from arq.connections import RedisSettings

from app.core.settings import settings
from app.core.logger import logger

# задачи
from app.workers.tasks.generate import queue_generation
# from app.workers.tasks.sora_reconcile import reconcile_sora
from app.workers.tasks.broadcast import broadcast_send

async def startup(ctx):
    logger.info("🚀 ARQ ready")

async def shutdown(ctx):
    logger.info("🔻 ARQ stop")

class WorkerSettings:
    # Обычные функции
    functions = [
        queue_generation,
        broadcast_send,
    ]
    # # CRON-джобы — отдельно!
    # cron_jobs = [
    #            cron(reconcile_sora, second=30, unique=True),
    # ]

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    burst = False

if __name__ == "__main__":
    asyncio.run(run_worker(WorkerSettings))
