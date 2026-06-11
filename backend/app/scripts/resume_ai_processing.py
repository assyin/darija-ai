"""Manually resume AI processing after the spend circuit breaker tripped.

This is the ONLY way to clear the pause (there is no auto-resume by design).
Review today's spend / the cause before running. Inside the backend container:
    docker exec -i infra-backend-1 python -m app.scripts.resume_ai_processing
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.services.ai.spend_guard import SpendGuard, today_ai_spend


async def main() -> None:
    settings = get_settings()
    redis = get_redis_client()
    try:
        guard = SpendGuard(redis=redis, hard_cap_usd=settings.ai_spend_daily_hard_cap_usd)
        was_paused = await guard.is_paused()
        spend = await today_ai_spend()
        if not was_paused:
            print("breaker was not paused — nothing to do.")
            return
        if spend >= settings.ai_spend_daily_hard_cap_usd:
            print(
                f"WARNING: today's spend ${spend:.4f} is still at/above the hard cap "
                f"${settings.ai_spend_daily_hard_cap_usd:.2f}. Clearing now will let the "
                f"breaker re-trip on the next article. Raise the cap or wait for the daily "
                f"reset if that is not intended."
            )
        await guard.clear()
        print(f"AI processing RESUMED (cleared pause flag). today_spend=${spend:.4f}")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
