from __future__ import annotations

from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

_settings = get_settings()

_redis_pool: ConnectionPool = ConnectionPool.from_url(
    _settings.redis_url_str,
    decode_responses=True,
    max_connections=20,
)


def get_redis_client() -> Redis:
    return Redis(connection_pool=_redis_pool)


async def get_redis() -> AsyncGenerator[Redis, None]:
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()


async def check_redis_health() -> bool:
    client = get_redis_client()
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()
