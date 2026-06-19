"""Unit tests for the SHADOW report builder (ERE MVP — Step 4).

Pure aggregation over the (already-tested) ranker: we pin counts, the
threshold-driven selected/deferred split, score-desc ordering with id tie-break,
the distribution, and the examples (near-misses).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.editorial.deterministic_ranker import RankInput
from app.services.editorial.shadow_report import ShadowCandidate, build_shadow_report

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
TIERS = {"TechCrunch AI": "A", "Numerama": "C"}
THRESHOLD = 55


def _fresh(h: float) -> datetime:
    return NOW - timedelta(hours=h)


def _cand(aid: int, title: str, content: str, source: str) -> ShadowCandidate:
    return ShadowCandidate(
        id=aid,
        rank_input=RankInput(
            title=title,
            content=content,
            source_name=source,
            published_at=_fresh(1),
            fetched_at=_fresh(1),
        ),
    )


# Two clearly-selected (high importance / MENA), two clearly-deferred (banal / off-topic).
_HIGH = _cand(
    101,
    "OpenAI raises $1 billion funding round",
    "AI startup machine learning gpt model",
    "Numerama",
)
_MENA = _cand(
    102,
    "Yassir lance une IA logistique au Maroc",
    "startup marocaine afrique fintech",
    "TechCrunch AI",
)
_BANAL = _cand(103, "A small tool tweak", "minor app change dashboard", "TechCrunch AI")
_OFFTOPIC = _cand(
    104, "Le festival de musique revient", "concerts en ville ce week-end", "Numerama"
)


def _build(cands):  # type: ignore[no-untyped-def]
    return build_shadow_report(cands, tiers=TIERS, now=NOW, threshold=THRESHOLD)


def test_counts_and_threshold_split() -> None:
    report = _build([_HIGH, _MENA, _BANAL, _OFFTOPIC])
    assert report.total == 4
    assert report.selected + report.deferred == report.total
    selected_ids = {a.id for a in report.rankings if a.decision == "selected"}
    assert selected_ids == {101, 102}  # high + MENA clear the bar
    assert report.selected == 2
    assert report.deferred == 2
    # every ranking's decision matches the threshold rule
    for a in report.rankings:
        assert a.decision == ("selected" if a.score >= THRESHOLD else "deferred")


def test_rankings_sorted_by_score_desc() -> None:
    report = _build([_BANAL, _OFFTOPIC, _HIGH, _MENA])
    scores = [a.score for a in report.rankings]
    assert scores == sorted(scores, reverse=True)


def test_tie_breaks_by_id_ascending() -> None:
    # Two identical inputs (same score) with different ids → lower id first.
    a = _cand(200, "OpenAI raises $1 billion", "AI startup gpt model", "Numerama")
    b = _cand(199, "OpenAI raises $1 billion", "AI startup gpt model", "Numerama")
    report = _build([a, b])
    assert report.rankings[0].score == report.rankings[1].score
    assert [r.id for r in report.rankings] == [199, 200]


def test_distribution_sums_to_total() -> None:
    report = _build([_HIGH, _MENA, _BANAL, _OFFTOPIC])
    assert set(report.distribution) == {"<40", "40-54", "55-69", "70-84", "85+"}
    assert sum(report.distribution.values()) == report.total


def test_top_and_examples() -> None:
    report = _build([_HIGH, _MENA, _BANAL, _OFFTOPIC])
    # top is score-desc prefix
    assert report.top == report.rankings[: len(report.top)]
    # examples are subsets of their group
    assert all(a.decision == "selected" for a in report.selected_examples)
    assert all(a.decision == "deferred" for a in report.deferred_examples)
    # deferred near-misses are the highest-scored deferred first
    deferred_scores = [a.score for a in report.deferred_examples]
    assert deferred_scores == sorted(deferred_scores, reverse=True)


def test_empty_corpus() -> None:
    report = _build([])
    assert report.total == 0
    assert report.selected == 0
    assert report.deferred == 0
    assert report.rankings == []
    assert sum(report.distribution.values()) == 0
