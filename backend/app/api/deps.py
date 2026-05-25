from __future__ import annotations

from fastapi import Request

from app.core.config import get_settings
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis_client


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def public_rate_limit(request: Request) -> None:
    """Per-IP rate limit for public endpoints (60 req/min/IP by default).

    Fail-open on Redis errors (handled inside ``check_rate_limit``).
    """
    settings = get_settings()
    await check_rate_limit(
        get_redis_client(),
        f"public:{client_ip(request)}",
        settings.public_rate_limit_max_requests,
        settings.public_rate_limit_window_seconds,
    )
