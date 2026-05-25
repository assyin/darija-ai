from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlmodel import col

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.raw_article import RawArticle

log = get_logger("workers.jobs.retry_failed")

# Re-process at most this many failed articles per tick.
RETRY_BATCH_LIMIT = 50


async def retry_failed(ctx: dict[str, Any]) -> dict[str, int]:
    """Re-enqueue ``process_one`` for articles left in the ``failed`` state.

    ``ArticleProcessor`` moves them back to ``processing`` on the next attempt,
    so transient errors (API timeouts, image-service blips) self-heal over time.
    """
    async with AsyncSessionLocal() as session:
        rows = await session.scalars(
            select(RawArticle)
            .where(col(RawArticle.processing_status) == "failed")
            .order_by(col(RawArticle.fetched_at))
            .limit(RETRY_BATCH_LIMIT)
        )
        ids = [r.id for r in rows if r.id is not None]

    for raw_article_id in ids:
        await ctx["redis"].enqueue_job("process_one", raw_article_id)

    log.info("retry_failed.enqueued", count=len(ids))
    return {"enqueued": len(ids)}
