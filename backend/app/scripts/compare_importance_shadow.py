"""Offline comparison of the importance lever: ranker v1 vs v1_1 (READ-ONLY).

Measures the ISOLATED impact of the "Strategic Importance + Actors" lever
(``importance_model="v1_1"``) against the production v1.0 scorer, over the
current pending corpus. It writes NOTHING, changes NO status, calls NO LLM, and
touches NO workflow — it only SELECTs and PRINTS. The live shadow path keeps
using ``rank()`` with the default ``importance_model="v1"`` (unchanged).

Because v1_1 importance is monotone (>= v1), no article can move
selected -> deferred; only deferred -> selected ("newly-selected") can happen.
Newly-selected articles are cross-referenced against the frozen human-baseline
labels (Step 6.5) to split them into recovered false-negatives (KEEP) vs new
false-positives (REJECT), and to recompute precision / recall / agreement.

Run inside the backend container:
    docker exec -i infra-backend-1 python -m app.scripts.compare_importance_shadow
    docker exec -i infra-backend-1 python -m app.scripts.compare_importance_shadow 200
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlmodel import col

from app.core.config import SOURCE_TIERS, get_settings
from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.raw_article import RawArticle
from app.models.source import Source
from app.services.editorial.deterministic_ranker import RankInput, RankResult, rank

log = get_logger("scripts.compare_importance_shadow")

# Frozen human-baseline labels (docs/HUMAN_BASELINE_AUDIT_STEP_6_5.md §1+§2).
# Used ONLY to score the lever on the labelled subset still present in pending.
_HUMAN_KEEP: frozenset[int] = frozenset(
    {
        # §1 shadow-selected, judged KEEP
        2203,
        2264,
        1992,
        2151,
        2262,
        2217,
        2134,
        2185,
        2172,
        1986,
        2064,
        2133,
        2231,
        2094,
        2167,
        # §2 deferred, judged KEEP (the strategic false-negatives)
        2000,
        2214,
        2219,
        2195,
        2221,
        2213,
        2042,
        2157,
        2178,
        2187,
        2188,
        # newly-selected dossier labels (Round-2 review), judged KEEP
        2215,
        2092,
        2301,
        2011,
        2225,
    }
)
_HUMAN_REJECT: frozenset[int] = frozenset(
    {
        # §1 shadow-selected, judged REJECT
        2271,
        2193,
        2066,
        2102,
        2272,
        2181,
        2145,
        2089,
        2200,
        2086,
        # §2 deferred, judged REJECT
        2268,
        2288,
        2261,
        2119,
        2226,
        2283,
        2282,
        2017,
        2168,
        2082,
        2156,
        2233,
        2024,
        2276,
        # newly-selected dossier labels (Round-2 review), judged REJECT/DROP
        2253,
        2091,
        2224,
        2278,
        1984,
        2162,
    }
)


async def _load_pending(limit: int | None) -> list[tuple[int, RankInput]]:
    """Read-only load of pending articles + their source name. No writes."""
    stmt = (
        select(RawArticle)
        .where(col(RawArticle.processing_status) == "pending")
        .order_by(col(RawArticle.fetched_at).desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    async with AsyncSessionLocal() as session:
        raws = list((await session.scalars(stmt)).all())
        sources = (await session.scalars(select(Source))).all()
    src_map: dict[int, str] = {int(s.id): s.name for s in sources if s.id is not None}

    items: list[tuple[int, RankInput]] = []
    for r in raws:
        assert r.id is not None  # persisted rows always have a PK
        items.append(
            (
                r.id,
                RankInput(
                    title=r.original_title or "",
                    content=r.original_content or "",
                    source_name=src_map.get(r.source_id, "unknown"),
                    published_at=r.published_at,
                    fetched_at=r.fetched_at,
                ),
            )
        )
    return items


def _human(article_id: int) -> str:
    if article_id in _HUMAN_KEEP:
        return "KEEP"
    if article_id in _HUMAN_REJECT:
        return "REJECT"
    return "—"


def _metrics(rows: list[tuple[int, RankResult]], model: str) -> dict[str, float | int]:
    """Confusion + precision/recall/agreement on the labelled subset only."""
    tp = fp = fn = tn = 0
    for article_id, res in rows:
        label = _human(article_id)
        if label == "—":
            continue
        selected = res.decision == "selected"
        if selected and label == "KEEP":
            tp += 1
        elif selected and label == "REJECT":
            fp += 1
        elif not selected and label == "KEEP":
            fn += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    agreement = (tp + tn) / n if n else 0.0
    return {
        "model": model,  # type: ignore[dict-item]
        "labelled": n,
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "agreement": round(agreement, 3),
    }


def _print_report(
    paired: list[tuple[int, RankInput, RankResult, RankResult]],
    threshold: int,
) -> None:
    sel_v1 = sum(1 for _, _, v1, _ in paired if v1.decision == "selected")
    sel_v11 = sum(1 for _, _, _, v11 in paired if v11.decision == "selected")
    newly = [
        (aid, item, v1, v11)
        for aid, item, v1, v11 in paired
        if v1.decision == "deferred" and v11.decision == "selected"
    ]
    regressions = [
        aid
        for aid, _, v1, v11 in paired
        if v1.decision == "selected" and v11.decision == "deferred"
    ]

    print("=" * 104)
    print("ERE IMPORTANCE LEVER — v1 vs v1_1 COMPARISON (READ ONLY · no DB write · offline)")
    print("=" * 104)
    print(
        f"threshold={threshold}  |  analyzed={len(paired)}  |  "
        f"selected v1={sel_v1}  ->  v1_1={sel_v11}  (Δ {sel_v11 - sel_v1:+d})"
    )
    print(
        f"monotonicity check: selected->deferred regressions = {len(regressions)} "
        f"(MUST be 0){'' if not regressions else '  !! ' + str(regressions)}"
    )

    keep = [n for n in newly if _human(n[0]) == "KEEP"]
    rej = [n for n in newly if _human(n[0]) == "REJECT"]
    unl = [n for n in newly if _human(n[0]) == "—"]
    print(f"\n--- Newly-selected (deferred under v1, selected under v1_1): {len(newly)} ---")
    print(
        f"    recovered FN (KEEP)={len(keep)}  |  new FP (REJECT)={len(rej)}  |  "
        f"unlabelled={len(unl)}"
    )
    for aid, item, v1, v11 in sorted(newly, key=lambda x: x[3].score, reverse=True):
        d = v11.breakdown["importance_detail"]
        lab = d.get("strategic_label", "—")
        print(
            f"  #{aid:<6} {_human(aid):6} v1={v1.score:3}->v1_1={v11.score:3} "
            f"imp {v1.breakdown['importance']:2}->{v11.breakdown['importance']:2} "
            f"strat={d.get('strategic_category', 0):2}({lab:18}) act={d['actors']:1}  "
            f"{item.source_name[:16]:16} {item.title[:46]}"
        )

    print("\n--- Labelled-subset metrics (only baseline ids still pending) ---")
    m_v1 = _metrics([(a, v1) for a, _, v1, _ in paired], "v1")
    m_v11 = _metrics([(a, v11) for a, _, _, v11 in paired], "v1_1")
    print(
        f"  {'model':6} {'N':>3} {'TP':>3} {'FP':>3} {'FN':>3} "
        f"{'TN':>3} {'prec':>6} {'rec':>6} {'agree':>6}"
    )
    for m in (m_v1, m_v11):
        print(
            f"  {m['model']!s:6} {m['labelled']:3} {m['TP']:3} {m['FP']:3} "
            f"{m['FN']:3} {m['TN']:3} {m['precision']:6} {m['recall']:6} {m['agreement']:6}"
        )
    print("=" * 104)


async def main(limit: int | None) -> None:
    settings = get_settings()
    threshold = settings.editorial_ranking_min_score
    now = datetime.now(UTC)
    items = await _load_pending(limit)

    paired: list[tuple[int, RankInput, RankResult, RankResult]] = []
    for aid, item in items:
        v1 = rank(item, tiers=SOURCE_TIERS, now=now, threshold=threshold, importance_model="v1")
        v11 = rank(item, tiers=SOURCE_TIERS, now=now, threshold=threshold, importance_model="v1_1")
        paired.append((aid, item, v1, v11))

    _print_report(paired, threshold)

    sel_v1 = sum(1 for _, _, v1, _ in paired if v1.decision == "selected")
    sel_v11 = sum(1 for _, _, _, v11 in paired if v11.decision == "selected")
    log.info(
        "compare_importance_shadow.done",
        mode="offline_compare",
        analyzed=len(paired),
        selected_v1=sel_v1,
        selected_v1_1=sel_v11,
        threshold=threshold,
        wrote_db=False,
    )


if __name__ == "__main__":
    arg_limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(arg_limit))
