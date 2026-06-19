"""Manual SHADOW run of the deterministic ranker over pending articles.

SHADOW = READ-ONLY. This script SELECTs pending raw_articles, ranks them with
the deterministic ranker, and PRINTS a report of what the ranker WOULD decide.
It writes NOTHING to the database, changes NO status, selects/rejects NOTHING
for real, calls NO LLM, and touches NO existing workflow (process_pending is
untouched). It is meant to be launched by hand only — it is NOT scheduled.

Run inside the backend container:
    docker exec -i infra-backend-1 python -m app.scripts.rank_pending_shadow
    docker exec -i infra-backend-1 python -m app.scripts.rank_pending_shadow 50   # limit
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
from app.services.editorial.deterministic_ranker import RankInput
from app.services.editorial.shadow_report import (
    ArticleRanking,
    ShadowCandidate,
    ShadowReport,
    build_shadow_report,
)

log = get_logger("scripts.rank_pending_shadow")


async def _load_pending(limit: int | None) -> list[ShadowCandidate]:
    """Read-only load of pending articles + their source name. No writes.

    Single-entity ``scalars()`` (codebase pattern) for clean typing; the source
    names are loaded once into a small id→name map.
    """
    stmt = (
        select(RawArticle)
        .where(col(RawArticle.processing_status) == "pending")
        .order_by(col(RawArticle.fetched_at).desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    candidates: list[ShadowCandidate] = []
    async with AsyncSessionLocal() as session:
        raws = list((await session.scalars(stmt)).all())
        sources = (await session.scalars(select(Source))).all()
    src_map: dict[int, str] = {int(s.id): s.name for s in sources if s.id is not None}
    for r in raws:
        assert r.id is not None  # persisted rows always have a PK
        candidates.append(
            ShadowCandidate(
                id=r.id,
                rank_input=RankInput(
                    title=r.original_title or "",
                    content=r.original_content or "",
                    source_name=src_map.get(r.source_id, "unknown"),
                    published_at=r.published_at,
                    fetched_at=r.fetched_at,
                ),
            )
        )
    return candidates


def _line(a: ArticleRanking) -> str:
    b = a.breakdown
    title = a.title[:58]
    return (
        f"  #{a.id:<6} score={a.score:3} [{a.decision:8}] "
        f"imp={b['importance']:2} rel={b['relevance']:2} mena={b['mena']:2} "
        f"src={b['source']:2}({b['source_tier']}) fresh={b['freshness']:2}  "
        f"{a.source_name[:18]:18}  {title}"
    )


def _print_report(report: ShadowReport, threshold: int) -> None:
    print("=" * 100)
    print("ERE SHADOW RANKING REPORT — READ ONLY (no DB write, no status change)")
    print("=" * 100)
    print(
        f"threshold={threshold}  |  analyzed={report.total}  |  "
        f"shadow_selected={report.selected}  |  shadow_deferred={report.deferred}"
    )
    print("\n--- Score distribution ---")
    for band, count in report.distribution.items():
        bar = "#" * min(count, 60)
        print(f"  {band:6} {count:4}  {bar}")
    print(f"\n--- Top {len(report.top)} by score ---")
    for a in report.top:
        print(_line(a))
    print("\n--- Shadow SELECTED examples ---")
    for a in report.selected_examples:
        print(_line(a))
    if not report.selected_examples:
        print("  (none cleared the threshold)")
    print("\n--- Shadow DEFERRED near-misses (highest-scored deferred) ---")
    for a in report.deferred_examples:
        print(_line(a))
    print("=" * 100)


async def main(limit: int | None) -> None:
    settings = get_settings()
    threshold = settings.editorial_ranking_min_score
    candidates = await _load_pending(limit)
    report = build_shadow_report(
        candidates,
        tiers=SOURCE_TIERS,
        now=datetime.now(UTC),
        threshold=threshold,
    )
    _print_report(report, threshold)
    log.info(
        "rank_pending_shadow.done",
        mode="shadow",
        analyzed=report.total,
        shadow_selected=report.selected,
        shadow_deferred=report.deferred,
        threshold=threshold,
        wrote_db=False,
    )


if __name__ == "__main__":
    arg_limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(arg_limit))
