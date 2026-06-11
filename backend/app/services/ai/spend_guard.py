"""Hard circuit breaker for AI spend.

CLAUDE.md §1 caps infra at $50/mo and §5 mandates a $5/day alert. Before this
module the daily check only *alerted* (Sentry) — it never *stopped* anything,
so a backlog flush or a runaway loop could drain the whole Anthropic balance
before anyone reacted (see the 2026-06-08 outage RCA).

:class:`SpendGuard` turns the soft alert into an enforcing gate. Evaluated
*before every article* (in ``process_one``), it:

  1. checks a Redis pause flag — if set, AI processing is paused (skip, no call);
  2. otherwise sums today's Claude spend and, if it has reached the hard cap,
     **trips the flag** (pause) and skips.

It is also tripped immediately on a billing/quota error so we stop hammering a
dead account. The flag has **no TTL**: once tripped, processing stays paused
until a human clears it (``app/scripts/resume_ai_processing.py``). This is the
intended safety behaviour — never silently auto-resume into a drain.

Every trip emits a CRITICAL structured log + a Sentry message that states the
pause is **voluntary and preventive**, with the spend and cap.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
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

# Redis key for the pause flag. Stored value is a JSON record (reason, spend,
# cap, tripped_at) for observability; presence alone means "paused".
PAUSE_KEY = "ai:paused"

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


class SpendGuard:
    """Enforcing daily spend gate backed by a Redis pause flag.

    ``spend_fn`` is injectable so tests can drive the spend without a DB. In
    production it defaults to :func:`today_ai_spend`.
    """

    def __init__(
        self,
        *,
        redis: Redis,
        hard_cap_usd: float,
        spend_fn: SpendFn = today_ai_spend,
    ) -> None:
        self._redis = redis
        self._cap = Decimal(str(hard_cap_usd))
        self._spend_fn = spend_fn

    async def is_paused(self) -> bool:
        return (await self._redis.get(PAUSE_KEY)) is not None

    async def allow(self) -> tuple[bool, str | None, Decimal]:
        """Gate one unit of AI work.

        Returns ``(allowed, reason, today_spend)``. When ``allowed`` is False
        the caller MUST skip all AI calls. ``reason`` is ``already_paused`` when
        the breaker was tripped earlier, or ``daily_cap_reached`` when this call
        tripped it.
        """
        if await self.is_paused():
            return False, "already_paused", Decimal("0")
        spend = await self._spend_fn()
        if spend >= self._cap:
            await self.trip("daily_cap_reached", spend)
            return False, "daily_cap_reached", spend
        return True, None, spend

    async def trip(self, reason: str, spend: Decimal) -> None:
        """Pause AI processing (idempotent). No-op if already paused."""
        if await self.is_paused():
            return
        payload = json.dumps(
            {
                "reason": reason,
                "spend_usd": str(spend),
                "hard_cap_usd": str(self._cap),
                "tripped_at": datetime.now(UTC).isoformat(),
            }
        )
        await self._redis.set(PAUSE_KEY, payload)  # no TTL → manual resume only
        message = (
            f"🛑 AI processing PAUSED (preventive, voluntary). reason={reason}, "
            f"today_spend=${spend:.4f}, hard_cap=${self._cap:.2f}. "
            f"Manual resume required (clear Redis key '{PAUSE_KEY}')."
        )
        log.critical(
            "ai.spend_guard.tripped",
            reason=reason,
            spend_usd=str(spend),
            hard_cap_usd=str(self._cap),
            message=message,
        )
        if sentry_sdk is not None:
            sentry_sdk.capture_message(message, level="error")

    async def clear(self) -> bool:
        """Manual resume — remove the pause flag. Returns True if one existed."""
        removed = bool(await self._redis.delete(PAUSE_KEY))
        log.warning("ai.spend_guard.cleared", removed=removed)
        return removed
