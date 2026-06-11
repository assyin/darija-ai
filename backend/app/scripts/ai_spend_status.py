"""Show the AI spend circuit-breaker state and today's Claude spend.

Read-only. Run inside the backend container:
    docker exec -i infra-backend-1 python -m app.scripts.ai_spend_status
"""

from __future__ import annotations

import asyncio
import json

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.services.ai.spend_guard import PAUSE_KEY, today_ai_spend


async def main() -> None:
    settings = get_settings()
    redis = get_redis_client()
    try:
        raw = await redis.get(PAUSE_KEY)
        spend = await today_ai_spend()
        cap = settings.ai_spend_daily_hard_cap_usd
        paused = raw is not None
        print(f"hard_cap_usd     : ${cap:.2f}")
        print(f"today_spend_usd  : ${spend:.4f}")
        print(f"breaker_state    : {'PAUSED' if paused else 'running'}")
        if paused:
            try:
                rec = json.loads(raw)
                print(f"  tripped_reason : {rec.get('reason')}")
                print(f"  tripped_at     : {rec.get('tripped_at')}")
                print(f"  spend_at_trip  : ${rec.get('spend_usd')}")
            except (json.JSONDecodeError, TypeError):
                print(f"  raw_flag       : {raw!r}")
            print("  resume with    : python -m app.scripts.resume_ai_processing")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
