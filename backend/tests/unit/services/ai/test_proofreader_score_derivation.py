"""Unit tests for the Proofreader v4 score derivation.

The contract this pins (v4, weighted-average aggregation):

  - When all four sub-scores arrive, the top-level ``score`` is the
    naturalness-weighted average (40/25/20/15), rounded to int.
  - When the model returns a divergent top-level (it must — schema still
    requires one), the server overrides with the derived weighted average.
  - When sub-scores are missing (legacy v1/v2 cached entries, partial
    responses), we fall back to the model's reported top-level.
  - When nothing is parseable, score=0 rather than crashing.
  - Garbage / out-of-range sub-scores are clamped to [0, 100].

History:
  - v2 used score = MIN(sub-scores). Diagnosed 2026-06-07 as anchoring
    everything to a (85, 75, 80, 80) template → 0 articles ever flagged
    ready to publish. v4 weighted average + naturalness floor (the floor
    lives in the auto-flag layer, not here) restores discrimination.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.proofread import ProofreadResult

# --- Test harness ------------------------------------------------------------


def _fake_openai_response(payload: dict[str, Any]) -> Any:
    """Build a duck-typed AsyncOpenAI response with the given JSON payload."""
    import json

    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = 1500
    usage.completion_tokens = 800
    usage.total_tokens = 2300
    response.usage = usage
    return response


async def _run_proofread(payload: dict[str, Any]) -> ProofreadResult:
    """Patch the OpenAI client + Redis, run proofread() once, return the result."""
    from app.services.ai.proofreader import Proofreader

    redis_client = MagicMock()
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=None)
    redis_client.delete = AsyncMock(return_value=None)

    with patch("app.services.ai.proofreader.AsyncOpenAI") as MockOpenAI:
        instance = MagicMock()
        instance.chat.completions.create = AsyncMock(return_value=_fake_openai_response(payload))
        MockOpenAI.return_value = instance
        with patch(
            "app.services.ai.proofreader.persist_ai_log",
            new=AsyncMock(),
        ):
            pr = Proofreader(api_key="sk-test", redis_client=redis_client)
            return await pr.proofread(text="body text", lang="darija", field="body")


def _weighted(g: int, n: int, c: int, k: int) -> int:
    """Replicate the prod formula so the tests are self-documenting."""
    return round(0.15 * g + 0.40 * n + 0.25 * c + 0.20 * k)


# --- Tests -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_is_naturalness_weighted_average() -> None:
    """Canonical case: 4 sub-scores → server computes weighted avg, overrides model."""
    result = await _run_proofread(
        {
            "grammar_score": 92,
            "naturalness_score": 78,
            "clarity_score": 85,
            "consistency_score": 88,
            "score": 78,  # model self-reports something; server overrides
            "summary": "ok",
            "suggestions": [],
        }
    )
    # 0.15*92 + 0.40*78 + 0.25*85 + 0.20*88 = 13.8 + 31.2 + 21.25 + 17.6 = 83.85 → 84
    assert result.score == _weighted(92, 78, 85, 88)
    assert result.score == 84
    assert result.grammar_score == 92
    assert result.naturalness_score == 78
    assert result.clarity_score == 85
    assert result.consistency_score == 88


@pytest.mark.asyncio
async def test_server_overrides_model_score_when_subscores_present() -> None:
    """Model reports a wildly different headline; weighted avg wins."""
    result = await _run_proofread(
        {
            "grammar_score": 90,
            "naturalness_score": 70,
            "clarity_score": 95,
            "consistency_score": 85,
            "score": 50,  # nonsense from the model
            "summary": "ok",
            "suggestions": [],
        }
    )
    # 0.15*90 + 0.40*70 + 0.25*95 + 0.20*85 = 13.5 + 28 + 23.75 + 17 = 82.25 → 82
    assert result.score == _weighted(90, 70, 95, 85)
    assert result.score == 82


@pytest.mark.asyncio
async def test_naturalness_dominates_aggregation() -> None:
    """Two articles with identical avg but inverted nat/gram score differently."""
    high_nat = await _run_proofread(
        {
            "grammar_score": 70,
            "naturalness_score": 90,
            "clarity_score": 80,
            "consistency_score": 80,
            "score": 80,
            "summary": "",
            "suggestions": [],
        }
    )
    low_nat = await _run_proofread(
        {
            "grammar_score": 90,
            "naturalness_score": 70,
            "clarity_score": 80,
            "consistency_score": 80,
            "score": 80,
            "summary": "",
            "suggestions": [],
        }
    )
    # Same arithmetic average (80) but naturalness weight makes them differ.
    assert high_nat.score > low_nat.score
    assert high_nat.score == _weighted(70, 90, 80, 80)  # 82
    assert low_nat.score == _weighted(90, 70, 80, 80)  # 78


@pytest.mark.asyncio
async def test_legacy_response_without_subscores_falls_back_to_model_score() -> None:
    """A cached/older response without sub-scores keeps working."""
    result = await _run_proofread(
        {
            "score": 82,
            "summary": "legacy",
            "suggestions": [],
        }
    )
    assert result.score == 82
    assert result.grammar_score is None
    assert result.naturalness_score is None
    assert result.clarity_score is None
    assert result.consistency_score is None


@pytest.mark.asyncio
async def test_partial_subscores_fall_back_to_model_score() -> None:
    """If any of the 4 sub-scores is missing, fall back to the model's headline."""
    result = await _run_proofread(
        {
            "grammar_score": 90,
            "naturalness_score": 72,
            # clarity_score + consistency_score absent
            "score": 75,
            "summary": "partial",
            "suggestions": [],
        }
    )
    # Cannot compute weighted avg without all four — server uses model's 75.
    assert result.score == 75
    assert result.grammar_score == 90
    assert result.naturalness_score == 72
    assert result.clarity_score is None
    assert result.consistency_score is None


@pytest.mark.asyncio
async def test_garbage_subscores_treated_as_missing() -> None:
    """Non-numeric sub-scores are dropped (treated as None); fall-through applies."""
    result = await _run_proofread(
        {
            "grammar_score": "not a number",
            "naturalness_score": None,
            "clarity_score": 80,
            "consistency_score": 90,
            "score": 80,
            "summary": "garbage",
            "suggestions": [],
        }
    )
    # Two of four sub-scores are unusable → fall back to the model's 80.
    assert result.score == 80
    assert result.grammar_score is None
    assert result.naturalness_score is None


@pytest.mark.asyncio
async def test_no_parseable_score_returns_zero() -> None:
    """Pathological response with no usable score must not crash."""
    result = await _run_proofread(
        {
            "summary": "nothing useful",
            "suggestions": [],
        }
    )
    assert result.score == 0


@pytest.mark.asyncio
async def test_subscores_clamped_to_0_100() -> None:
    """A drifting model returns 120 or -5 — we clamp on read, then aggregate."""
    result = await _run_proofread(
        {
            "grammar_score": 120,
            "naturalness_score": -5,
            "clarity_score": 85,
            "consistency_score": 88,
            "score": 70,
            "summary": "clamped",
            "suggestions": [],
        }
    )
    assert result.grammar_score == 100
    assert result.naturalness_score == 0
    # 0.15*100 + 0.40*0 + 0.25*85 + 0.20*88 = 15 + 0 + 21.25 + 17.6 = 53.85 → 54
    assert result.score == _weighted(100, 0, 85, 88)
    assert result.score == 54
