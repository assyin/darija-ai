"""Unit tests for cache-aware ``compute_cost``.

Pins the multipliers (1.25x write surcharge, 0.10x read discount) against
each Haiku/Sonnet/Opus rate. Anthropic publishes these as fixed ratios; if
they ever change, these tests fail loudly and force a coordinated update.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.ai.pricing import (
    CACHE_READ_MULTIPLIER,
    CACHE_WRITE_MULTIPLIER,
    compute_cost,
)


def test_no_cache_args_back_compat() -> None:
    """v1 callers that don't pass cache args still compute the same cost."""
    # Haiku 4.5: $1/M in, $5/M out.
    # 1000 in + 500 out → 1000*1/1M + 500*5/1M = $0.001 + $0.0025 = $0.0035
    cost = compute_cost("claude-haiku-4-5", 1000, 500)
    assert cost == Decimal("0.003500")


def test_cache_write_costs_125_percent_of_input_rate() -> None:
    """Cache write tokens pay a 25% premium over normal input."""
    # 1000 cache_creation tokens at Haiku $1/M → 1000 * 1 * 1.25 / 1M = $0.00125
    cost = compute_cost(
        "claude-haiku-4-5", input_tokens=0, output_tokens=0, cache_creation_tokens=1000
    )
    assert cost == Decimal("0.001250")
    # Confirm the multiplier publicly exposed matches what the test pins.
    assert Decimal("1.25") == CACHE_WRITE_MULTIPLIER


def test_cache_read_costs_10_percent_of_input_rate() -> None:
    """Cache read tokens cost 10% of normal input — the whole point of caching."""
    # 10_000 cache_read tokens at Haiku → 10_000 * 1 * 0.10 / 1M = $0.001
    cost = compute_cost(
        "claude-haiku-4-5", input_tokens=0, output_tokens=0, cache_read_tokens=10_000
    )
    assert cost == Decimal("0.001000")
    assert Decimal("0.10") == CACHE_READ_MULTIPLIER


def test_full_mix_input_creation_read_output() -> None:
    """All four buckets compose linearly — sanity check the formula."""
    # 500 fresh input + 200 cache_write + 10_000 cache_read + 1_500 output
    # = (500*1 + 200*1.25 + 10_000*0.10 + 1_500*5) / 1M
    # = (500 + 250 + 1_000 + 7_500) / 1M
    # = 9_250 / 1M
    # = $0.00925
    cost = compute_cost(
        "claude-haiku-4-5",
        input_tokens=500,
        output_tokens=1_500,
        cache_creation_tokens=200,
        cache_read_tokens=10_000,
    )
    assert cost == Decimal("0.009250")


def test_realistic_localizer_call_with_cache_hit() -> None:
    """Anchored on Jun 6 prod numbers — confirm we'd cut ~85% off a hit.

    Localizer v3 system prompt = 15_618 tokens. Article body = ~5_000 tokens.
    Output ~1_600 tokens.

    Without caching (cold first call): pays all 15_618 + 5_000 at $1/M and
    1_600 at $5/M = $0.0286.

    With cache hit: 15_618 tokens at 10% + 5_000 fresh at 100% + output at
    100% = (15_618*0.10 + 5_000 + 1_600*5) / 1M = (1_562 + 5_000 + 8_000) /
    1M = $0.01456 — about 49% cheaper than cold.
    """
    cold = compute_cost("claude-haiku-4-5", 20_618, 1_600)
    hit = compute_cost(
        "claude-haiku-4-5",
        input_tokens=5_000,
        output_tokens=1_600,
        cache_read_tokens=15_618,
    )
    # Hit must be cheaper than cold, and at least 40% cheaper for the saving
    # claim in the rollout report to hold.
    assert hit < cold
    savings_ratio = (cold - hit) / cold
    assert savings_ratio > Decimal("0.4")


def test_unknown_model_returns_zero_silently() -> None:
    """Regression — unknown models must not crash the cost path."""
    assert compute_cost("definitely-not-a-real-model", 1000, 500) == Decimal("0")
    # And the cache args don't change that.
    assert compute_cost(
        "definitely-not-a-real-model",
        1000,
        500,
        cache_creation_tokens=100,
        cache_read_tokens=1000,
    ) == Decimal("0")


@pytest.mark.parametrize(
    "model,in_rate",
    [
        ("claude-haiku-4-5", Decimal("1")),
        ("claude-sonnet-4-6", Decimal("3")),
        ("claude-opus-4-7", Decimal("5")),
    ],
)
def test_cache_multipliers_consistent_across_claude_family(model: str, in_rate: Decimal) -> None:
    """The 1.25x / 0.10x cache ratios apply uniformly across Claude tiers."""
    # 1_000 cache_creation tokens → in_rate * 1.25 * 1000 / 1M
    expected_write = in_rate * Decimal("1.25") * Decimal("1000") / Decimal("1000000")
    got_write = compute_cost(model, 0, 0, cache_creation_tokens=1_000)
    assert got_write == expected_write.quantize(Decimal("0.000001"))

    # 1_000 cache_read tokens → in_rate * 0.10 * 1000 / 1M
    expected_read = in_rate * Decimal("0.10") * Decimal("1000") / Decimal("1000000")
    got_read = compute_cost(model, 0, 0, cache_read_tokens=1_000)
    assert got_read == expected_read.quantize(Decimal("0.000001"))
