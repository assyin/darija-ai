"""Manually resume AI processing after the spend circuit breaker tripped.

This is the ONLY way to clear an EMERGENCY pause (billing/quota failure or the
monthly guardrail) — there is no auto-resume for those by design. A BUDGET pause
(daily cap) auto-resumes at UTC midnight on its own, but this script clears it
too for an immediate resume. Review today's / this month's spend before running.

Inside the backend container:
    docker exec -i infra-backend-1 python -m app.scripts.resume_ai_processing
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.services.ai.spend_guard import SpendGuard, month_ai_spend, today_ai_spend


async def main() -> None:
    settings = get_settings()
    redis = get_redis_client()
    try:
        guard = SpendGuard(
            redis=redis,
            hard_cap_usd=settings.ai_spend_daily_hard_cap_usd,
            monthly_cap_usd=settings.ai_monthly_cap_usd,
        )
        emergency = await guard.is_emergency_paused()
        budget = await guard.is_budget_paused()
        if not emergency and not budget:
            print("breaker was not paused — nothing to do.")
            return

        today = await today_ai_spend()
        month = await month_ai_spend()
        print(f"pause state      : emergency={emergency} budget={budget}")
        daily_cap = settings.ai_spend_daily_hard_cap_usd
        monthly_cap = settings.ai_monthly_cap_usd
        print(f"today_spend_usd  : ${today:.4f} (daily cap ${daily_cap:.2f})")
        print(f"month_spend_usd  : ${month:.4f} (monthly cap ${monthly_cap:.2f})")
        if today >= daily_cap:
            print(
                "WARNING: today's spend is still at/above the DAILY cap — the budget "
                "breaker will re-trip on the next article (auto-resumes at UTC midnight)."
            )
        if month >= monthly_cap:
            print(
                "WARNING: this month's spend is at/above the MONTHLY cap — the emergency "
                "breaker will re-trip immediately. Raise the monthly cap or wait for the "
                "1st of next month if that is not intended."
            )

        await guard.clear()
        print(f"AI processing RESUMED (cleared all flags). today=${today:.4f} month=${month:.4f}")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
