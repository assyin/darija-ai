"""Tests for the AI spend circuit breaker — V2 (budget vs emergency).

Safety-critical contracts pinned here:
  * daily cap → BUDGET pause that AUTO-resumes at UTC midnight (TTL set);
  * billing error / monthly cap → EMERGENCY pause that is STICKY (no TTL,
    manual resume only) — never auto-resumes into a dead account or a breach;
  * the legacy V1 key is honoured as an emergency pause (safe rollout);
  * manual clear removes every pause flag.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest
from redis.asyncio import Redis

from app.services.ai.spend_guard import (
    BUDGET_PAUSE_KEY,
    EMERGENCY_PAUSE_KEY,
    LEGACY_PAUSE_KEY,
    SpendGuard,
    seconds_until_utc_midnight,
)


class FakeRedis:
    """Minimal async Redis stand-in with TTL recording."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.ttl[key] = ex

    async def delete(self, key: str) -> int:
        self.ttl.pop(key, None)
        return 1 if self.store.pop(key, None) is not None else 0


def _spend(value: str) -> Callable[[], Awaitable[Decimal]]:
    async def _fn() -> Decimal:
        return Decimal(value)

    return _fn


def _guard(
    fake: FakeRedis,
    *,
    cap: float = 2.0,
    monthly: float = 50.0,
    spend: str = "0.00",
    month: str = "0.00",
) -> SpendGuard:
    return SpendGuard(
        redis=cast(Redis, fake),
        hard_cap_usd=cap,
        monthly_cap_usd=monthly,
        spend_fn=_spend(spend),
        month_spend_fn=_spend(month),
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allows_when_below_both_caps_and_not_paused() -> None:
    fake = FakeRedis()
    guard = _guard(fake, spend="1.50", month="10.00")
    allowed, reason, spend = await guard.allow()
    assert allowed is True
    assert reason is None
    assert spend == Decimal("1.50")
    assert await guard.is_paused() is False


# ---------------------------------------------------------------------------
# Budget pause (daily cap) — auto-resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_cap_trips_budget_pause_with_ttl() -> None:
    fake = FakeRedis()
    guard = _guard(fake, cap=2.0, spend="2.00")  # >= daily cap
    allowed, reason, spend = await guard.allow()
    assert allowed is False
    assert reason == "daily_cap_reached"
    assert spend == Decimal("2.00")
    # Budget key set, with a TTL to midnight (auto-resume); NOT an emergency.
    assert BUDGET_PAUSE_KEY in fake.store
    assert 1 <= fake.ttl[BUDGET_PAUSE_KEY] <= 86400
    assert await guard.is_budget_paused() is True
    assert await guard.is_emergency_paused() is False


@pytest.mark.asyncio
async def test_budget_pause_persists_within_day() -> None:
    fake = FakeRedis()
    await _guard(fake, cap=2.0, spend="2.50").allow()  # trips budget
    # A later call (even at $0 spend) stays paused until the TTL expires.
    allowed, reason, _ = await _guard(fake, cap=2.0, spend="0.00").allow()
    assert allowed is False
    assert reason == "budget_paused"


@pytest.mark.asyncio
async def test_trip_budget_is_idempotent() -> None:
    fake = FakeRedis()
    guard = _guard(fake)
    await guard.trip_budget("daily_cap_reached", Decimal("2.00"))
    first = fake.store[BUDGET_PAUSE_KEY]
    await guard.trip_budget("daily_cap_reached", Decimal("9.99"))  # no-op
    assert fake.store[BUDGET_PAUSE_KEY] == first


# ---------------------------------------------------------------------------
# Emergency pause — sticky (billing + monthly guardrail)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_billing_error_trips_sticky_emergency_pause() -> None:
    fake = FakeRedis()
    guard = _guard(fake, spend="0.10")  # well under cap
    await guard.trip_emergency("billing_error", Decimal("0.10"))
    # Sticky: no TTL, blocks regardless of spend.
    assert EMERGENCY_PAUSE_KEY in fake.store
    assert EMERGENCY_PAUSE_KEY not in fake.ttl
    allowed, reason, _ = await guard.allow()
    assert allowed is False
    assert reason == "emergency_paused"


@pytest.mark.asyncio
async def test_monthly_cap_trips_emergency_pause() -> None:
    fake = FakeRedis()
    guard = _guard(fake, monthly=50.0, spend="0.00", month="50.00")  # at monthly cap
    allowed, reason, spend = await guard.allow()
    assert allowed is False
    assert reason == "monthly_cap_reached"
    assert spend == Decimal("50.00")
    assert EMERGENCY_PAUSE_KEY in fake.store
    assert EMERGENCY_PAUSE_KEY not in fake.ttl  # sticky, no auto-resume


@pytest.mark.asyncio
async def test_monthly_cap_takes_precedence_over_daily() -> None:
    fake = FakeRedis()
    # Both caps exceeded → the sticky monthly emergency wins (not the budget pause).
    guard = _guard(fake, cap=2.0, monthly=50.0, spend="5.00", month="60.00")
    allowed, reason, _ = await guard.allow()
    assert allowed is False
    assert reason == "monthly_cap_reached"
    assert BUDGET_PAUSE_KEY not in fake.store


@pytest.mark.asyncio
async def test_trip_emergency_is_idempotent_keeps_first_record() -> None:
    fake = FakeRedis()
    guard = _guard(fake)
    await guard.trip_emergency("billing_error", Decimal("0"))
    first = fake.store[EMERGENCY_PAUSE_KEY]
    await guard.trip_emergency("monthly_cap_reached", Decimal("99"))  # no-op
    assert fake.store[EMERGENCY_PAUSE_KEY] == first
    assert "billing_error" in first


# ---------------------------------------------------------------------------
# Legacy V1 key — honoured as emergency (safe rollout)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_pause_key_is_honoured_as_emergency() -> None:
    fake = FakeRedis()
    fake.store[LEGACY_PAUSE_KEY] = '{"reason": "daily_cap_reached"}'
    guard = _guard(fake, spend="0.00", month="0.00")
    assert await guard.is_emergency_paused() is True
    allowed, reason, _ = await guard.allow()
    assert allowed is False
    assert reason == "emergency_paused"


# ---------------------------------------------------------------------------
# Manual clear
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_clear_removes_all_pause_flags() -> None:
    fake = FakeRedis()
    guard = _guard(fake)
    await guard.trip_emergency("billing_error", Decimal("0"))
    await guard.trip_budget("daily_cap_reached", Decimal("2"))
    fake.store[LEGACY_PAUSE_KEY] = "{}"
    assert await guard.is_paused() is True

    removed = await guard.clear()
    assert removed is True
    assert await guard.is_paused() is False
    assert fake.store == {}
    # Clearing again is a no-op.
    assert await guard.clear() is False


# ---------------------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------------------


def test_seconds_until_utc_midnight() -> None:
    assert seconds_until_utc_midnight(datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)) == 12 * 3600
    assert seconds_until_utc_midnight(datetime(2026, 6, 19, 23, 59, 59, tzinfo=UTC)) == 1
    assert seconds_until_utc_midnight(datetime(2026, 6, 19, 0, 0, 0, tzinfo=UTC)) == 86400
