from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlmodel import col

from app.core.db import AsyncSessionLocal
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.models.raw_article import RawArticle
from app.services.ai.claude_client import is_billing_error
from app.services.ai.spend_guard import SpendGuard
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
    """Run the full localization pipeline for a single raw article.

    Gated by :class:`SpendGuard`: before any Claude call we check the hard
    daily-spend circuit breaker. When tripped, the article is left untouched
    (``pending``) and NO AI call is made — the breaker stays paused until a
    human clears it. A billing/quota error trips the breaker immediately so we
    stop hammering a dead account.
    """
    settings = ctx["settings"]
    redis = ctx["cache_redis"]
    guard = SpendGuard(redis=redis, hard_cap_usd=settings.ai_spend_daily_hard_cap_usd)

    allowed, reason, spend = await guard.allow()
    if not allowed:
        log.warning(
            "process_one.ai_paused",
            raw_article_id=raw_article_id,
            reason=reason,
            today_spend_usd=str(spend),
        )
        return {
            "raw_article_id": raw_article_id,
            "status": "skipped_paused",
            "article_id": None,
            "quality_passed": False,
        }

    processor = ArticleProcessor.from_settings(settings, redis)
    try:
        outcome = await processor.process(raw_article_id)
    except ExternalServiceError as exc:
        # A billing/quota outage must immediately pause the pipeline rather than
        # let retry_failed / process_pending keep re-attempting (and re-failing)
        # against a dead account.
        detail = str(exc.details.get("error", "")) if exc.details else ""
        if is_billing_error(detail) or is_billing_error(exc.message):
            await guard.trip("billing_error", spend)
        raise
    return {
        "raw_article_id": outcome.raw_article_id,
        "status": outcome.status,
        "article_id": outcome.article_id,
        "quality_passed": outcome.quality_passed,
    }
