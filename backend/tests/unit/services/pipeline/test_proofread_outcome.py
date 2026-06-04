"""Unit tests for the in-pipeline auto-flag proofread step.

Exercises ``ArticleProcessor._proofread_or_skip`` (and its interaction with
``_persist_draft`` via a fake) — no DB, no OpenAI calls.

The contract these tests pin:

  - When the Proofreader is disabled, the outcome is empty and the score
    columns are not touched (``proofread_at`` stays None).
  - When both languages clear the configured threshold, ready_to_publish
    is true.
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


def _fake_processor(*, proofreader: Any, threshold: int = 85) -> ArticleProcessor:
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
    )


def _result(score: int) -> ProofreadResult:
    return ProofreadResult(
        score=score,
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
    assert outcome.proofread_at is None  # ← critical: upsert path won't touch existing scores


# --- Happy paths -------------------------------------------------------------


@pytest.mark.asyncio
async def test_both_scores_above_threshold_is_ready() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[_result(90), _result(88)])
    proc = _fake_processor(proofreader=pr, threshold=85)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija == 90
    assert outcome.score_fr == 88
    assert outcome.ready_to_publish is True
    assert outcome.proofread_at is not None


@pytest.mark.asyncio
async def test_darija_only_clears_threshold_when_fr_absent() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[_result(86)])  # called once
    proc = _fake_processor(proofreader=pr, threshold=85)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr=None,
    )

    assert outcome.score_darija == 86
    assert outcome.score_fr is None
    assert outcome.ready_to_publish is True
    # Proofreader called once (Darija only) — never for FR when content_fr is None.
    assert pr.proofread.await_count == 1


# --- Threshold edges ---------------------------------------------------------


@pytest.mark.asyncio
async def test_darija_below_threshold_blocks_ready() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[_result(70), _result(95)])
    proc = _fake_processor(proofreader=pr, threshold=85)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija == 70
    assert outcome.score_fr == 95
    assert outcome.ready_to_publish is False


@pytest.mark.asyncio
async def test_fr_below_threshold_blocks_ready() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[_result(95), _result(60)])
    proc = _fake_processor(proofreader=pr, threshold=85)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija == 95
    assert outcome.score_fr == 60
    assert outcome.ready_to_publish is False


@pytest.mark.asyncio
async def test_exact_threshold_is_ready() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[_result(85), _result(85)])
    proc = _fake_processor(proofreader=pr, threshold=85)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )
    assert outcome.ready_to_publish is True


# --- Fail-soft semantics -----------------------------------------------------


@pytest.mark.asyncio
async def test_fr_failure_does_not_zero_darija_score() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[_result(92), RuntimeError("openai 503")])
    proc = _fake_processor(proofreader=pr, threshold=85)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija == 92
    assert outcome.score_fr is None
    # Surviving Darija clears threshold; missing FR is treated as "not blocking".
    assert outcome.ready_to_publish is True
    assert outcome.proofread_at is not None


@pytest.mark.asyncio
async def test_darija_failure_does_not_zero_fr_score() -> None:
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[RuntimeError("openai 503"), _result(92)])
    proc = _fake_processor(proofreader=pr, threshold=85)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija is None
    assert outcome.score_fr == 92
    # Darija missing → cannot claim ready (Darija = source-of-truth).
    assert outcome.ready_to_publish is False
    # But proofread_at is set because at least one score landed.
    assert outcome.proofread_at is not None


@pytest.mark.asyncio
async def test_both_failures_leave_proofread_at_none() -> None:
    """Critical: with no score at all, the upsert path must not clobber existing scores."""
    pr = MagicMock()
    pr.proofread = AsyncMock(side_effect=[RuntimeError("dr"), RuntimeError("fr")])
    proc = _fake_processor(proofreader=pr, threshold=85)

    outcome = await proc._proofread_or_skip(
        raw_article_id=1,
        content_darija="dr body",
        content_fr="fr body",
    )

    assert outcome.score_darija is None
    assert outcome.score_fr is None
    assert outcome.ready_to_publish is False
    assert outcome.proofread_at is None  # ← contract for _persist_draft upsert branch
