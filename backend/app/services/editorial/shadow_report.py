"""Shadow report builder for the deterministic ranker (ERE MVP — Step 4).

SHADOW = pure analysis, ZERO side effects. This module turns a list of candidate
articles into a structured report of what the ranker WOULD decide — it never
writes the DB, never changes a status, never selects/rejects for real, never
calls an LLM. The runner (``app/scripts/rank_pending_shadow.py``) feeds it
read-only data and prints the result.

Pure & deterministic: depends only on its arguments (``tiers``, ``now``,
``threshold`` are injected, like the ranker itself).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.editorial.deterministic_ranker import RankInput, rank

# Score bands for the distribution view (matches the daily-report spec §8b).
_BANDS: tuple[tuple[str, int, int], ...] = (
    ("<40", 0, 40),
    ("40-54", 40, 55),
    ("55-69", 55, 70),
    ("70-84", 70, 85),
    ("85+", 85, 101),
)
_TOP_N = 20
_EXAMPLES_N = 5


@dataclass(frozen=True)
class ShadowCandidate:
    """One article to rank, paired with its DB id (read-only — no status)."""

    id: int
    rank_input: RankInput


@dataclass(frozen=True)
class ArticleRanking:
    id: int
    title: str
    source_name: str
    published_at: datetime | None
    fetched_at: datetime
    score: int
    decision: str  # SHADOW decision — NOT persisted, NOT acted on
    breakdown: dict[str, Any]


@dataclass(frozen=True)
class ShadowReport:
    total: int
    selected: int
    deferred: int
    rankings: list[ArticleRanking]  # all, sorted by score desc
    distribution: dict[str, int]  # band label -> count
    top: list[ArticleRanking]  # top _TOP_N by score
    selected_examples: list[ArticleRanking]
    deferred_examples: list[ArticleRanking]  # highest-scored deferred = near-misses


def _band(score: int) -> str:
    for label, lo, hi in _BANDS:
        if lo <= score < hi:
            return label
    return _BANDS[-1][0]


def build_shadow_report(
    candidates: Sequence[ShadowCandidate],
    *,
    tiers: Mapping[str, str],
    now: datetime,
    threshold: int,
) -> ShadowReport:
    """Rank every candidate and summarize — pure, no I/O, no mutation."""
    rankings: list[ArticleRanking] = []
    for c in candidates:
        r = rank(c.rank_input, tiers=tiers, now=now, threshold=threshold)
        rankings.append(
            ArticleRanking(
                id=c.id,
                title=c.rank_input.title,
                source_name=c.rank_input.source_name,
                published_at=c.rank_input.published_at,
                fetched_at=c.rank_input.fetched_at,
                score=r.score,
                decision=r.decision,
                breakdown=r.breakdown,
            )
        )

    # Stable sort: score desc, then id asc for determinism on ties.
    rankings.sort(key=lambda a: (-a.score, a.id))

    selected = [a for a in rankings if a.decision == "selected"]
    deferred = [a for a in rankings if a.decision == "deferred"]

    distribution = {label: 0 for label, _, _ in _BANDS}
    for a in rankings:
        distribution[_band(a.score)] += 1

    return ShadowReport(
        total=len(rankings),
        selected=len(selected),
        deferred=len(deferred),
        rankings=rankings,
        distribution=distribution,
        top=rankings[:_TOP_N],
        selected_examples=selected[:_EXAMPLES_N],
        deferred_examples=deferred[:_EXAMPLES_N],
    )
