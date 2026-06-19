"""Pipeline SHADOW recorder for the deterministic ranker (ERE MVP — Step 5).

When ``editorial_ranking_shadow_enabled`` is ON, ``process_one`` calls this once
per processed article to record what the ranker WOULD decide — purely as
observation. It writes ONLY the decoupled shadow columns (``editorial_score`` /
``editorial_decision`` / ``score_breakdown``), NEVER ``processing_status``,
NEVER a real selection or publication, NEVER an LLM. It is fully fail-soft: any
error is logged and swallowed so the pipeline is never affected. When the flag
is OFF it is a one-line no-op.

SHADOW-default model: the ``v1_1`` importance composite (tightened Strategic
Importance + Actors), validated offline on the live corpus (0 new FP on the
human baseline, precision + recall up vs v1). This is OBSERVE-ONLY — it does NOT
enforce: nothing here makes ``editorial_decision`` affect what the pipeline
localizes or publishes.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.raw_article import RawArticle
from app.models.source import Source
from app.services.editorial.deterministic_ranker import RankInput, rank

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger("services.editorial.shadow_recorder")

SessionFactory = Callable[[], "AsyncSession"]


async def maybe_record_shadow_ranking(
    raw_article_id: int,
    *,
    enabled: bool,
    threshold: int,
    tiers: Mapping[str, str],
    session_factory: SessionFactory = AsyncSessionLocal,
    now: datetime | None = None,
) -> bool:
    """Record the SHADOW ranking for one article.

    Returns True if a score was recorded, False otherwise (flag off, missing
    row, or a swallowed error). SHADOW-only: writes editorial_* columns, NEVER
    ``processing_status``. Fully fail-soft.
    """
    if not enabled:
        return False

    when = now or datetime.now(UTC)
    try:
        async with session_factory() as session:
            raw = await session.get(RawArticle, raw_article_id)
            if raw is None:
                return False
            source = await session.get(Source, raw.source_id)
            source_name = source.name if source is not None else "unknown"

            result = rank(
                RankInput(
                    title=raw.original_title or "",
                    content=raw.original_content or "",
                    source_name=source_name,
                    published_at=raw.published_at,
                    fetched_at=raw.fetched_at,
                ),
                tiers=tiers,
                now=when,
                threshold=threshold,
                importance_model="v1_1",  # SHADOW-default (tightened); observe-only, no enforce
            )

            breakdown = dict(result.breakdown)
            breakdown["computed_at"] = when.isoformat()

            # SHADOW write — decoupled columns ONLY. processing_status untouched.
            raw.editorial_score = result.score
            raw.editorial_decision = result.decision
            raw.score_breakdown = breakdown
            await session.commit()

        log.info(
            "editorial.shadow_recorded",
            raw_article_id=raw_article_id,
            score=result.score,
            decision=result.decision,
            source_tier=result.breakdown["source_tier"],
            computed_at=when.isoformat(),
        )
        return True
    except Exception as exc:  # fail-soft — NEVER break the pipeline
        log.warning(
            "editorial.shadow_record_failed",
            raw_article_id=raw_article_id,
            error=str(exc),
            error_type=exc.__class__.__name__,
        )
        return False
