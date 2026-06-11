"""Tests for the AI spend circuit breaker.

The safety-critical contract: once today's spend reaches the hard cap (or a
billing error fires), the breaker trips a Redis flag that pauses all AI work
and STAYS tripped until manually cleared — never auto-resumes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import cast

import pytest
from redis.asyncio import Redis

from app.services.ai.spend_guard import PAUSE_KEY, SpendGuard


class FakeRedis:
    """Minimal async Redis stand-in (string store) for the flag."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0


def _spend(value: str) -> Callable[[], Awaitable[Decimal]]:
    async def _fn() -> Decimal:
        return Decimal(value)

    return _fn


def _guard(fake: FakeRedis, *, cap: float, spend: str) -> SpendGuard:
    return SpendGuard(redis=cast(Redis, fake), hard_cap_usd=cap, spend_fn=_spend(spend))


@pytest.mark.asyncio
async def test_allows_when_below_cap_and_not_paused() -> None:
    fake = FakeRedis()
    guard = _guard(fake, cap=2.0, spend="1.50")
    allowed, reason, spend = await guard.allow()
    assert allowed is True
    assert reason is None
    assert spend == Decimal("1.50")
    assert await guard.is_paused() is False


@pytest.mark.asyncio
async def test_trips_when_spend_reaches_cap() -> None:
    fake = FakeRedis()
    guard = _guard(fake, cap=2.0, spend="2.00")  # >= cap
    allowed, reason, spend = await guard.allow()
    assert allowed is False
    assert reason == "daily_cap_reached"
    assert spend == Decimal("2.00")
    assert await guard.is_paused() is True
    assert PAUSE_KEY in fake.store


@pytest.mark.asyncio
async def test_stays_paused_on_next_call_even_if_spend_drops() -> None:
    fake = FakeRedis()
    # First call trips at/over cap.
    await _guard(fake, cap=2.0, spend="2.50").allow()
    # A later call with the SAME redis but lower spend must remain paused
    # (no auto-resume) and report already_paused without re-summing.
    allowed, reason, _ = await _guard(fake, cap=2.0, spend="0.00").allow()
    assert allowed is False
    assert reason == "already_paused"


@pytest.mark.asyncio
async def test_manual_clear_resumes() -> None:
    fake = FakeRedis()
    guard = _guard(fake, cap=2.0, spend="2.00")
    await guard.allow()  # trips
    assert await guard.is_paused() is True
    removed = await guard.clear()
    assert removed is True
    assert await guard.is_paused() is False
    # Clearing again is a no-op.
    assert await guard.clear() is False


@pytest.mark.asyncio
async def test_trip_is_idempotent_keeps_first_record() -> None:
    fake = FakeRedis()
    guard = _guard(fake, cap=2.0, spend="0.00")
    await guard.trip("billing_error", Decimal("0"))
    first = fake.store[PAUSE_KEY]
    await guard.trip("daily_cap_reached", Decimal("9.99"))  # must be a no-op
    assert fake.store[PAUSE_KEY] == first
    assert "billing_error" in first


@pytest.mark.asyncio
async def test_billing_trip_pauses_regardless_of_spend() -> None:
    fake = FakeRedis()
    guard = _guard(fake, cap=2.0, spend="0.10")  # well under cap
    await guard.trip("billing_error", Decimal("0.10"))
    assert await guard.is_paused() is True
    allowed, reason, _ = await guard.allow()
    assert allowed is False
    assert reason == "already_paused"
