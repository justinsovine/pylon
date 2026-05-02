import json

import redis.asyncio as redis

from .config import settings


async def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url)


async def set_progress(pipeline_id: str, data: dict, ttl: int = 120) -> None:
    r = await get_redis()
    try:
        await r.set(f"pylon:progress:{pipeline_id}", json.dumps(data), ex=ttl)
    finally:
        await r.aclose()


async def get_progress(pipeline_id: str) -> dict | None:
    r = await get_redis()
    try:
        raw = await r.get(f"pylon:progress:{pipeline_id}")
        return json.loads(raw) if raw else None
    finally:
        await r.aclose()
