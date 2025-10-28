# app/utils/idempotency.py
from typing import Optional
from redis.asyncio import Redis

async def once(redis: Redis, key: str, ttl_sec: int = 600) -> bool:
    ok = await redis.setnx(key, "1")
    if ok:
        await redis.expire(key, ttl_sec)
    return bool(ok)

def make_key(prefix: str, identifier: str) -> str:
    return f"idemp:{prefix}:{identifier}"
