"""Unit tests for the Proofreader v2 score derivation.

The contract this pins:

  - When all four sub-scores arrive, the top-level ``score`` is the MIN.
  - When the model returns a divergent top-level (e.g. its own average),
    the server overrides with the derived min and logs a warning.
  - When sub-scores are missing (v1 cached entries, partial responses),
    we fall back to the model's reported score.
  - When nothing is parseable, score=0 rather than crashing.

We unit-test the derivation logic in isolation by reading the proofreader
module's parse/derive block via a small fake response payload — no OpenAI
calls, no Redis.
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
        instance.chat.completions.create = AsyncMock(
            return_value=_fake_openai_response(payload)
        )
        MockOpenAI.return_value = instance
        with patch(
            "app.services.ai.proofreader.persist_ai_log",
            new=AsyncMock(),
        ):
            pr = Proofreader(api_key="sk-test", redis_client=redis_client)
            return await pr.proofread(text="body text", lang="darija", field="body")


# --- Tests -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_is_min_of_subscores() -> None:
    result = await _run_proofread(
        {
            "grammar_score": 92,
            "naturalness_score": 78,
            "clarity_score": 85,
            "consistency_score": 88,
            "score": 78,  # model self-reports the correct min
            "summary": "ok",
            "suggestions": [],
        }
    )
    assert result.score == 78
    assert result.grammar_score == 92
    assert result.naturalness_score == 78
    assert result.clarity_score == 85
    assert result.consistency_score == 88


@pytest.mark.asyncio
async def test_server_overrides_drifting_model_score() -> None:
    """Model claims 85 (avg), but min(sub) = 70 — server must use 70."""
    result = await _run_proofread(
        {
            "grammar_score": 90,
            "naturalness_score": 70,
            "clarity_score": 95,
            "consistency_score": 85,
            "score": 85,  # ← wrong; should be 70
            "summary": "ok",
            "suggestions": [],
        }
    )
    assert result.score == 70  # server-derived, not model-reported


@pytest.mark.asyncio
async def test_legacy_v1_response_falls_back_to_model_score() -> None:
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
async def test_partial_subscores_use_min_of_available() -> None:
    """Two sub-scores arrive, two are missing — use the min of what we have."""
    result = await _run_proofread(
        {
            "grammar_score": 90,
            "naturalness_score": 72,
            "score": 75,
            "summary": "partial",
            "suggestions": [],
        }
    )
    # min(90, 72) = 72 — server overrides the model's 75.
    assert result.score == 72
    assert result.grammar_score == 90
    assert result.naturalness_score == 72
    assert result.clarity_score is None
    assert result.consistency_score is None


@pytest.mark.asyncio
async def test_garbage_subscores_are_dropped() -> None:
    """Non-numeric sub-scores are treated as missing, no crash."""
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
    assert result.score == 80  # min(80, 90)
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
    """A drifting model returns 120 or -5 — we clamp on read."""
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
    # min(100, 0, 85, 88) = 0
    assert result.score == 0
