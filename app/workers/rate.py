# app/workers/rate.py
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

class RateLimiter:
    """
    Ограничение:
      - rps: глобально не больше N запросов в секунду
      - concurrency: не больше M задач одновременно

    Использование:
        limiter = RateLimiter(rps=25, concurrency=20)
        await limiter.start()
        async with limiter.ticket():
            await do_work()
        await limiter.stop()
    """
    def __init__(self, rps: int = 10, concurrency: int = 5) -> None:
        self.rps = max(int(rps or 0), 0)
        self.interval = 1.0 / self.rps if self.rps > 0 else 0.0
        self._sem = asyncio.Semaphore(max(int(concurrency or 1), 1))
        self._lock = asyncio.Lock()
        self._last_ts = 0.0
        self._started = False

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    @asynccontextmanager
    async def ticket(self):
        """
        Контекст, который:
          1) Учитывает параллелизм (semaphore)
          2) Уважает RPS: сериализует проход через lock, выдерживая интервал
        """
        await self._sem.acquire()
        try:
            if self._started and self.interval > 0:
                async with self._lock:
                    now = time.monotonic()
                    wait = self.interval - (now - self._last_ts)
                    if wait > 0:
                        await asyncio.sleep(wait)
                    self._last_ts = time.monotonic()
            yield
        finally:
            self._sem.release()
