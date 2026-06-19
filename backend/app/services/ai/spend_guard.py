"""Hard circuit breaker for AI spend — V2 (budget vs emergency).

V1 used a single sticky flag (`ai:paused`, no TTL) for BOTH "daily budget
reached" and "billing/quota failure". The sticky behaviour is correct for a
genuine failure (never auto-resume into a dead account — see the 2026-06-08
outage RCA) but creates daily operator toil for the normal budget case, and it
ignores the monthly ceiling (`$2/day x 30 = $60 > $50/mo` cap, CLAUDE.md §1).

V2 splits the two concerns:

  * **Budget pause** (`daily_cap_reached`) → key with a TTL to the next UTC
    midnight, so it AUTO-resumes exactly when today's spend window resets. No
    operator action needed.
  * **Emergency pause** (`billing_error`, `monthly_cap_reached`, or operator
    kill-switch) → STICKY key with no TTL, manual resume only. Preserves every
    V1 safety guarantee where it matters (dead account / monthly breach).

`allow()` (evaluated before every article in ``process_one``):
  1. emergency pause set → blocked (sticky);
  2. budget pause set → blocked (auto-expires at midnight);
  3. month-to-date spend ≥ monthly cap → trip EMERGENCY (sticky) and block;
  4. today's spend ≥ daily cap → trip BUDGET (auto-resume) and block;
  5. otherwise allow.

The legacy V1 key is still honoured as an emergency pause so a V2 rollout never
silently unpauses an already-paused production; the resume script clears it.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy import text

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

try:  # pragma: no cover - depends on prod settings module
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None  # type: ignore[assignment]

log = get_logger("services.ai.spend_guard")

# --- Pause keys ---
# Budget pause: daily cap reached. AUTO-resumes at UTC midnight (TTL) because
# today's spend window resets then. Recurring, expected, low severity.
BUDGET_PAUSE_KEY = "ai:paused:budget"
# Emergency pause: billing/quota failure or the monthly guardrail. STICKY (no
# TTL) — manual resume only, so we never auto-resume into a dead account or
# breach the monthly ceiling. Preserves the 2026-06-08 safety lesson.
EMERGENCY_PAUSE_KEY = "ai:paused:emergency"
# Legacy V1 key. Honoured as an emergency (sticky) pause so a V2 rollout never
# silently unpauses an already-paused production. Cleared by the resume script.
LEGACY_PAUSE_KEY = "ai:paused"
# Back-compat alias (importers / observability scripts).
PAUSE_KEY = LEGACY_PAUSE_KEY

SessionFactory = Callable[[], "AsyncSession"]
SpendFn = Callable[[], Awaitable[Decimal]]


async def today_ai_spend(session_factory: SessionFactory = AsyncSessionLocal) -> Decimal:
    """Sum of successful AI spend (all providers) since UTC midnight."""
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(cost_usd), 0)::numeric "
                    "FROM ai_logs "
                    "WHERE success = true AND created_at >= date_trunc('day', NOW())"
                )
            )
        ).one()
    return Decimal(str(row[0]))


async def month_ai_spend(session_factory: SessionFactory = AsyncSessionLocal) -> Decimal:
    """Sum of successful AI spend (all providers) since the 1st of the UTC month."""
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(cost_usd), 0)::numeric "
                    "FROM ai_logs "
                    "WHERE success = true AND created_at >= date_trunc('month', NOW())"
                )
            )
        ).one()
    return Decimal(str(row[0]))


def seconds_until_utc_midnight(now: datetime) -> int:
    """Whole seconds from ``now`` to the next UTC midnight (always >= 1)."""
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


class SpendGuard:
    """Enforcing spend gate with a split budget/emergency pause model.

    ``spend_fn`` / ``month_spend_fn`` are injectable so tests can drive spend
    without a DB. In production they default to the ``ai_logs`` aggregates.
    """

    def __init__(
        self,
        *,
        redis: Redis,
        hard_cap_usd: float,
        monthly_cap_usd: float,
        spend_fn: SpendFn = today_ai_spend,
        month_spend_fn: SpendFn = month_ai_spend,
    ) -> None:
        self._redis = redis
        self._cap = Decimal(str(hard_cap_usd))
        self._monthly_cap = Decimal(str(monthly_cap_usd))
        self._spend_fn = spend_fn
        self._month_spend_fn = month_spend_fn

    async def _is_set(self, key: str) -> bool:
        return (await self._redis.get(key)) is not None

    async def is_emergency_paused(self) -> bool:
        """Sticky pause: a real emergency key OR the honoured legacy V1 key."""
        return await self._is_set(EMERGENCY_PAUSE_KEY) or await self._is_set(LEGACY_PAUSE_KEY)

    async def is_budget_paused(self) -> bool:
        return await self._is_set(BUDGET_PAUSE_KEY)

    async def is_paused(self) -> bool:
        return await self.is_emergency_paused() or await self.is_budget_paused()

    async def allow(self) -> tuple[bool, str | None, Decimal]:
        """Gate one unit of AI work. Returns ``(allowed, reason, spend)``.

        When ``allowed`` is False the caller MUST skip all AI calls.
        """
        # 1. Emergency pause (sticky) takes precedence — never auto-resumes.
        if await self.is_emergency_paused():
            return False, "emergency_paused", Decimal("0")
        # 2. Budget pause (auto-expires at UTC midnight).
        if await self.is_budget_paused():
            return False, "budget_paused", Decimal("0")
        # 3. Monthly guardrail → emergency (sticky): autonomy must not breach the
        #    monthly ceiling even though daily caps alone would allow it.
        month_spend = await self._month_spend_fn()
        if month_spend >= self._monthly_cap:
            await self.trip_emergency("monthly_cap_reached", month_spend)
            return False, "monthly_cap_reached", month_spend
        # 4. Daily hard cap → budget pause (auto-resumes next UTC day).
        spend = await self._spend_fn()
        if spend >= self._cap:
            await self.trip_budget("daily_cap_reached", spend)
            return False, "daily_cap_reached", spend
        return True, None, spend

    async def trip_budget(self, reason: str, spend: Decimal) -> None:
        """Budget pause (idempotent). TTL → auto-resume at next UTC midnight."""
        if await self.is_budget_paused():
            return
        now = datetime.now(UTC)
        ttl = seconds_until_utc_midnight(now)
        payload = json.dumps(
            {
                "kind": "budget",
                "reason": reason,
                "spend_usd": str(spend),
                "hard_cap_usd": str(self._cap),
                "tripped_at": now.isoformat(),
                "auto_resume": "next UTC midnight",
                "ttl_seconds": ttl,
            }
        )
        await self._redis.set(BUDGET_PAUSE_KEY, payload, ex=ttl)
        log.warning(
            "ai.spend_guard.budget_paused",
            reason=reason,
            spend_usd=str(spend),
            hard_cap_usd=str(self._cap),
            ttl_seconds=ttl,
            message=(
                f"AI processing BUDGET-paused (daily cap ${self._cap:.2f} reached, "
                f"today_spend=${spend:.4f}). Auto-resumes at UTC midnight (~{ttl}s)."
            ),
        )

    async def trip_emergency(self, reason: str, spend: Decimal) -> None:
        """Emergency pause (idempotent). STICKY — no TTL, manual resume only."""
        if await self.is_emergency_paused():
            return
        payload = json.dumps(
            {
                "kind": "emergency",
                "reason": reason,
                "spend_usd": str(spend),
                "hard_cap_usd": str(self._cap),
                "monthly_cap_usd": str(self._monthly_cap),
                "tripped_at": datetime.now(UTC).isoformat(),
            }
        )
        await self._redis.set(EMERGENCY_PAUSE_KEY, payload)  # no TTL → manual resume
        message = (
            f"🛑 AI processing EMERGENCY-paused (preventive, voluntary). reason={reason}, "
            f"spend=${spend:.4f}. Manual resume required "
            f"(python -m app.scripts.resume_ai_processing)."
        )
        log.critical(
            "ai.spend_guard.emergency_paused",
            reason=reason,
            spend_usd=str(spend),
            monthly_cap_usd=str(self._monthly_cap),
            message=message,
        )
        if sentry_sdk is not None:
            sentry_sdk.capture_message(message, level="error")

    async def clear(self) -> bool:
        """Manual full resume — remove budget, emergency, and legacy pauses.

        Returns True if at least one pause flag was removed.
        """
        removed = 0
        for key in (EMERGENCY_PAUSE_KEY, BUDGET_PAUSE_KEY, LEGACY_PAUSE_KEY):
            removed += int(await self._redis.delete(key))
        log.warning("ai.spend_guard.cleared", removed=removed)
        return removed > 0
