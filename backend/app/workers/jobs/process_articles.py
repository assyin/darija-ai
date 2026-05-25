from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlmodel import col

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.raw_article import RawArticle
from app.services.pipeline.article_processor import ArticleProcessor

log = get_logger("workers.jobs.process_articles")

# Safety cap so a backlog can't enqueue an unbounded burst in one tick.
PENDING_BATCH_LIMIT = 100


async def process_pending(ctx: dict[str, Any]) -> dict[str, int]:
    """Enqueue one ``process_one`` job per pending raw article.

    Each article is processed as an independent, individually-retryable job
    rather than in a single long-running task.
    """
    async with AsyncSessionLocal() as session:
        rows = await session.scalars(
            select(RawArticle)
            .where(col(RawArticle.processing_status) == "pending")
            .order_by(col(RawArticle.fetched_at))
            .limit(PENDING_BATCH_LIMIT)
        )
        ids = [r.id for r in rows if r.id is not None]

    for raw_article_id in ids:
        await ctx["redis"].enqueue_job("process_one", raw_article_id)

    log.info("process_pending.enqueued", count=len(ids))
    return {"enqueued": len(ids)}


async def process_one(ctx: dict[str, Any], raw_article_id: int) -> dict[str, Any]:
    """Run the full localization pipeline for a single raw article."""
    processor = ArticleProcessor.from_settings(ctx["settings"], ctx["cache_redis"])
    outcome = await processor.process(raw_article_id)
    return {
        "raw_article_id": outcome.raw_article_id,
        "status": outcome.status,
        "article_id": outcome.article_id,
        "quality_passed": outcome.quality_passed,
    }
