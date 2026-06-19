"""Show the AI spend circuit-breaker state and today's / this month's spend.

Read-only. Run inside the backend container:
    docker exec -i infra-backend-1 python -m app.scripts.ai_spend_status
"""

from __future__ import annotations

import asyncio
import json

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.services.ai.spend_guard import (
    BUDGET_PAUSE_KEY,
    EMERGENCY_PAUSE_KEY,
    LEGACY_PAUSE_KEY,
    month_ai_spend,
    today_ai_spend,
)


def _print_flag(label: str, raw: str | bytes | None) -> None:
    if raw is None:
        print(f"  {label:16}: clear")
        return
    print(f"  {label:16}: SET")
    try:
        rec = json.loads(raw)
        print(f"      reason     : {rec.get('reason')}")
        print(f"      tripped_at : {rec.get('tripped_at')}")
        print(f"      spend_usd  : ${rec.get('spend_usd')}")
    except (json.JSONDecodeError, TypeError):
        print(f"      raw_flag   : {raw!r}")


async def main() -> None:
    settings = get_settings()
    redis = get_redis_client()
    try:
        emergency = await redis.get(EMERGENCY_PAUSE_KEY)
        budget = await redis.get(BUDGET_PAUSE_KEY)
        legacy = await redis.get(LEGACY_PAUSE_KEY)
        today = await today_ai_spend()
        month = await month_ai_spend()

        paused = emergency is not None or budget is not None or legacy is not None
        print(f"daily_cap_usd    : ${settings.ai_spend_daily_hard_cap_usd:.2f}")
        print(f"monthly_cap_usd  : ${settings.ai_monthly_cap_usd:.2f}")
        print(f"today_spend_usd  : ${today:.4f}")
        print(f"month_spend_usd  : ${month:.4f}")
        print(f"breaker_state    : {'PAUSED' if paused else 'running'}")
        _print_flag("emergency", emergency)
        _print_flag("budget(auto)", budget)
        _print_flag("legacy", legacy)
        if paused:
            print("  resume with     : python -m app.scripts.resume_ai_processing")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
