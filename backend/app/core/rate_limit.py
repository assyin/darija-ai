from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.exceptions import RateLimitError
from app.core.logging import get_logger

logger = get_logger("core.rate_limit")


async def check_rate_limit(
    redis: Redis,  # type: ignore[type-arg]
    key: str,
    max_requests: int,
    window_seconds: int,
) -> None:
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            results = await pipe.execute()
        count = int(results[0])
    except RedisError:
        logger.warning("rate_limit.redis_error", key=key)
        return
    if count > max_requests:
        raise RateLimitError()
