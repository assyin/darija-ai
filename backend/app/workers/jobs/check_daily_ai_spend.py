"""Hourly check: fire a warning when today's AI spend crosses the threshold.

CLAUDE.md §5 mandates a $5/day Sentry alert. Before this PR the rule had no
implementation (no data source). With ``ai_logs`` populated by
``LoggingLLMProvider``, we can now query today's cumulative spend.

The job:
  - Queries ``SUM(cost_usd)`` for today (UTC).
  - If above ``settings.ai_spend_daily_threshold_usd`` and the alert has not
    yet fired today, emits both a structlog WARNING and a Sentry
    ``capture_message`` (when Sentry is configured).
  - Stores the last-firing date in Redis under
    ``ai_spend_alert:last_fired_date`` so we alert at most once per day.

Idempotency is intentional: rerunning the job after the alert has fired
that day is a no-op, but the threshold check itself remains observable in
the structlog stream.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sentry_sdk
from sqlalchemy import text

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger

log = get_logger("workers.check_daily_ai_spend")

_REDIS_KEY = "ai_spend_alert:last_fired_date"


async def _today_spend_usd() -> tuple[Decimal, int]:
    """Returns (total cost, call count) for successful AI calls since UTC midnight."""
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT COALESCE(SUM(cost_usd), 0)::numeric AS cost,
                           COUNT(*)::int AS calls
                    FROM ai_logs
                    WHERE success = true
                      AND created_at >= date_trunc('day', NOW())
                    """
                )
            )
        ).one()
    return Decimal(str(row.cost)), int(row.calls)


async def check_daily_ai_spend(ctx: dict[str, Any]) -> None:
    """arq cron job — see ``app/workers/settings.py``."""
    settings = ctx["settings"]
    redis = ctx.get("cache_redis")
    threshold = Decimal(str(settings.ai_spend_daily_threshold_usd))

    spend, calls = await _today_spend_usd()
    today_iso = datetime.now(UTC).date().isoformat()

    log.info(
        "ai_spend_check.tick",
        spend_usd=str(spend),
        calls=calls,
        threshold_usd=str(threshold),
        today=today_iso,
    )

    if spend < threshold:
        return

    # Above threshold — fire at most once per day.
    if redis is not None:
        last_fired = await redis.get(_REDIS_KEY)
        if last_fired is not None:
            # Redis decodes bytes by default; defensive cast.
            last_fired_str = last_fired.decode() if isinstance(last_fired, bytes) else last_fired
            if last_fired_str == today_iso:
                log.debug(
                    "ai_spend_check.alert_already_fired_today",
                    today=today_iso,
                    spend_usd=str(spend),
                )
                return

    message = (
        f"AI spend today is ${spend:.4f} ({calls} calls) — above the "
        f"${threshold:.2f}/day threshold."
    )
    log.warning(
        "ai_spend_check.threshold_crossed",
        spend_usd=str(spend),
        threshold_usd=str(threshold),
        calls=calls,
        today=today_iso,
    )
    # Sentry capture is a best-effort; if Sentry isn't configured this is a no-op.
    sentry_sdk.capture_message(message, level="warning")

    if redis is not None:
        # Expire ~26 h so we don't pin a stale key forever if cron clock drifts.
        await redis.set(_REDIS_KEY, today_iso, ex=26 * 3600)
