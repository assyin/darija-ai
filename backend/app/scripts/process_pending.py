"""Manual trigger: process all pending raw articles synchronously.

Mirrors what the ``process_pending`` + ``process_one`` worker jobs do, but runs
in-process without the arq queue — handy for local runs and debugging. The
scheduled worker (``make worker``) is the production path.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select
from sqlmodel import col

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.core.redis import get_redis_client
from app.models.raw_article import RawArticle
from app.services.pipeline.article_processor import ArticleProcessor


async def main() -> int:
    configure_logging()
    log = get_logger("scripts.process_pending")
    settings = get_settings()
    redis = get_redis_client()

    async with AsyncSessionLocal() as session:
        rows = await session.scalars(
            select(RawArticle)
            .where(col(RawArticle.processing_status) == "pending")
            .order_by(col(RawArticle.fetched_at))
        )
        ids = [r.id for r in rows if r.id is not None]

    if not ids:
        print("No pending articles.")
        await redis.aclose()
        await engine.dispose()
        return 0

    processor = ArticleProcessor.from_settings(settings, redis)
    counts = {"translated": 0, "rejected": 0, "failed": 0}
    try:
        for raw_article_id in ids:
            outcome = await processor.process(raw_article_id)
            counts[outcome.status] = counts.get(outcome.status, 0) + 1
            log.info(
                "process_pending.article_done",
                raw_article_id=raw_article_id,
                status=outcome.status,
                article_id=outcome.article_id,
            )
    finally:
        await redis.aclose()
        await engine.dispose()

    print(
        f"Processed {len(ids)} pending: "
        f"{counts['translated']} translated, "
        f"{counts['rejected']} rejected, "
        f"{counts['failed']} failed."
    )
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
