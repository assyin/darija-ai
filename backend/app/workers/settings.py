from __future__ import annotations

from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.redis import get_redis_client
from app.workers.jobs.check_daily_ai_spend import check_daily_ai_spend
from app.workers.jobs.fetch_articles import fetch_articles
from app.workers.jobs.process_articles import process_one, process_pending
from app.workers.jobs.retry_failed import retry_failed

log = get_logger("workers.settings")


async def on_startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    settings = get_settings()
    ctx["settings"] = settings
    # Dedicated client for the localizer's content-hash cache (separate from
    # arq's own pool at ctx["redis"], which is used for enqueueing jobs).
    ctx["cache_redis"] = get_redis_client()
    log.info("worker.startup", environment=settings.environment)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    cache_redis = ctx.get("cache_redis")
    if cache_redis is not None:
        await cache_redis.aclose()
    log.info("worker.shutdown")


class WorkerSettings:
    """arq worker entrypoint. Run with: ``arq app.workers.settings.WorkerSettings``.

    Combines the job queue and the periodic scheduler (arq cron) — no separate
    APScheduler process needed (decision D1).
    """

    redis_settings = RedisSettings.from_dsn(get_settings().redis_url_str)
    functions: ClassVar[list[Any]] = [
        fetch_articles,
        process_pending,
        process_one,
        retry_failed,
        check_daily_ai_spend,
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_tries = 3
    cron_jobs: ClassVar[list[Any]] = [
        # Ingest RSS sources every 30 minutes.
        cron(fetch_articles, minute={0, 30}),
        # Sweep for pending articles every 10 minutes (safety net for anything
        # not picked up by the post-fetch enqueue).
        cron(process_pending, minute={5, 15, 25, 35, 45, 55}),
        # Retry failed articles once an hour.
        cron(retry_failed, minute={20}),
        # Hourly AI-spend ceiling check (CLAUDE.md §5). Fires Sentry once
        # per day when today's spend crosses ai_spend_daily_threshold_usd.
        cron(check_daily_ai_spend, minute={50}),
    ]
