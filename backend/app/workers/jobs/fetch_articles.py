from __future__ import annotations

from typing import Any

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.services.scraping.ingestion import IngestionService
from app.services.scraping.rss_fetcher import RSSFetcher

log = get_logger("workers.jobs.fetch_articles")


async def fetch_articles(ctx: dict[str, Any]) -> dict[str, int]:
    """Fetch + dedup all active RSS sources into ``raw_articles`` (status pending).

    Thin job: delegates to ``IngestionService``, then enqueues ``process_pending``
    so freshly inserted articles are localized without waiting for the next cron.
    """
    service = IngestionService(rss_fetcher=RSSFetcher())
    async with AsyncSessionLocal() as session:
        results = await service.ingest_all_active(session)

    totals = {
        "fetched": sum(r.fetched for r in results),
        "inserted": sum(r.inserted for r in results),
        "skipped": sum(r.skipped for r in results),
        "rejected": sum(r.rejected for r in results),
        "sources": len(results),
    }
    log.info("fetch_articles.done", **totals)

    if totals["inserted"]:
        await ctx["redis"].enqueue_job("process_pending")

    return totals
