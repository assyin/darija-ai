"""Unit tests for the in-pipeline auto-flag proofread step.

Exercises ``ArticleProcessor._proofread_or_skip`` — no DB, no OpenAI calls.

The contract these tests pin (v4 aggregation + v3 naturalness floor):

  - When the Proofreader is disabled, the outcome is empty and the score
    columns are not touched (``proofread_at`` stays None).
  - When both languages clear BOTH the threshold AND the naturalness floor,
    ready_to_publish is true.
  - When the headline clears but naturalness is below the floor on the
    populated language, ready_to_publish is FALSE — even when the score
    is good (this is the gate the user wanted).
  - When the naturalness sub-score is missing (legacy cached entry, parse
    failure), it is treated as "unknown, not blocking" so we don't reject
    articles for a missing measurement.
  - When one language fails but the other clears, the surviving language
    drives the decision; a failure does NOT zero a passing score.
  - When BOTH languages fail, ``proofread_at`` is None so the upsert path
    leaves prior scores intact.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.proofread import ProofreadResult
from app.services.pipeline.article_processor import (
    ArticleProcessor,
    ProofreadOutcome,
)


def _fake_processor(
    *,
    proofreader: Any,
    threshold: int = 80,
    naturalness_floor: int = 75,
) -> ArticleProcessor:
    """Build an ArticleProcessor with only the proofreader wired.

    Other collaborators (localizer, quality_gate, …) are required by the
    constructor but unused by ``_proofread_or_skip``, so we pass MagicMocks
    to satisfy the typing.
    """
    return ArticleProcessor(
        localizer=MagicMock(),
        quality_gate=MagicMock(),
        image_generator=None,
        translator=None,
        proofreader=proofreader,
        proofread_publish_ready_threshold=threshold,
        proofread_naturalness_floor=naturalness_floor,
    )


def _result(score: int, *, naturalness: int | None = None) -> ProofreadResult:
    """Build a minimal ProofreadResult. Tests that need the naturalness floor
    to engage pass an explicit ``naturalness`` sub-score; legacy tests that
    don't care leave it None — which the v4 floor treats as 'not blocking'."""
    return ProofreadResult(
        score=score,
        naturalness_score=naturalness,
        summary="",
        suggestions=[],
        lang="darija",
        field="body",
        model="gpt-4o-mini",
        cached=False,
    )


# --- Proofreader disabled ----------------------------------------------------


@pytest.mark.asyncio
async def test_proofread_disabled_returns_empty_outcome() -> None:
    proc = _fake_processor(proofreader=None)
    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="anything",
        content_fr="anything",
    )
    assert outcome == ProofreadOutcome()
    assert outcome.ready_to_publish is False
    assert outcome.proofread_at is None  # critical: upsert path won't touch existing scores


# --- Happy paths -------------------------------------------------------------


@pytest.mark.asyncio
async def test_both_scores_and_naturalness_above_thresholds_is_ready() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(
        side_effect=[
            _result(85, naturalness=80),
            _result(82, naturalness=78),
        ]
    )
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija == 85
    assert outcome.score_fr == 82
    assert outcome.ready_to_publish is True
    assert outcome.proofread_at is not None


@pytest.mark.asyncio
async def test_darija_only_clears_when_fr_absent() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[_result(85, naturalness=80)])
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr=None,
    )

    assert outcome.score_darija == 85
    assert outcome.score_fr is None
    assert outcome.ready_to_publish is True
    assert pr.proofread.await_count == 1


# --- Threshold edges ---------------------------------------------------------


@pytest.mark.asyncio
async def test_darija_below_threshold_blocks_ready() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(
        side_effect=[
            _result(75, naturalness=80),
            _result(90, naturalness=85),
        ]
    )
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija == 75
    assert outcome.score_fr == 90
    assert outcome.ready_to_publish is False  # darija below threshold


@pytest.mark.asyncio
async def test_fr_below_threshold_blocks_ready() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(
        side_effect=[
            _result(90, naturalness=85),
            _result(70, naturalness=80),
        ]
    )
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija == 90
    assert outcome.score_fr == 70
    assert outcome.ready_to_publish is False  # fr below threshold


@pytest.mark.asyncio
async def test_exact_threshold_is_ready() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(
        side_effect=[
            _result(80, naturalness=75),  # both at floor
            _result(80, naturalness=75),
        ]
    )
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )
    assert outcome.ready_to_publish is True


# --- Naturalness floor (v3 gate) --------------------------------------------


@pytest.mark.asyncio
async def test_naturalness_below_floor_blocks_ready_even_when_score_clears() -> None:
    """The key v4 contract: a good headline score but weak naturalness must NOT pass."""
    pr = MagicMock()
    pr.proofread = AsyncMock(
        side_effect=[
            _result(82, naturalness=70),  # score clears 80; naturalness < 75
            _result(82, naturalness=78),
        ]
    )
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija == 82
    assert outcome.ready_to_publish is False  # naturalness floor engaged


@pytest.mark.asyncio
async def test_naturalness_floor_on_fr_blocks_ready() -> None:
    """Same gate applies to the French sub-score."""
    pr = MagicMock()
    pr.proofread = AsyncMock(
        side_effect=[
            _result(85, naturalness=82),
            _result(85, naturalness=72),  # FR naturalness too low
        ]
    )
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.ready_to_publish is False


@pytest.mark.asyncio
async def test_missing_naturalness_subscore_is_not_blocking() -> None:
    """Legacy cached entries lack the sub-score; treat as 'unknown, not blocking'."""
    pr = MagicMock()
    pr.proofread = AsyncMock(
        side_effect=[
            _result(85, naturalness=None),  # legacy entry, no sub-score
            _result(85, naturalness=None),
        ]
    )
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.ready_to_publish is True  # score clears, floor not enforced


# --- Fail-soft semantics -----------------------------------------------------


@pytest.mark.asyncio
async def test_fr_failure_does_not_zero_darija_score() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(
        side_effect=[
            _result(88, naturalness=82),
            RuntimeError("openai 503"),
        ]
    )
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija == 88
    assert outcome.score_fr is None
    # Surviving Darija clears threshold + floor; missing FR is not blocking.
    assert outcome.ready_to_publish is True
    assert outcome.proofread_at is not None


@pytest.mark.asyncio
async def test_darija_failure_does_not_zero_fr_score() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(
        side_effect=[
            RuntimeError("openai 503"),
            _result(90, naturalness=80),
        ]
    )
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija is None
    assert outcome.score_fr == 90
    # Darija missing → cannot claim ready (Darija = source-of-truth).
    assert outcome.ready_to_publish is False
    # But proofread_at is set because at least one score landed.
    assert outcome.proofread_at is not None


@pytest.mark.asyncio
async def test_both_failures_leave_proofread_at_none() -> None:
    """Critical: with no score at all, the upsert path must not clobber existing scores."""
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[RuntimeError("dr"), RuntimeError("fr")])
    proc = _fake_processor(proofreader=pr, threshold=80, naturalness_floor=75)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija is None
    assert outcome.score_fr is None
    assert outcome.ready_to_publish is False
    assert outcome.proofread_at is None  # contract for _persist_draft upsert branch
