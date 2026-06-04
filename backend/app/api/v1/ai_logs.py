"""Admin AI cost dashboard endpoint.

Reads from the ``ai_logs`` table (populated by ``LoggingLLMProvider`` and
``persist_ai_log`` — see RCA 2026-06-04). One endpoint returns the whole
dashboard payload to keep the frontend simple: a single fetch, all aggregates.

Time windows are computed against ``NOW()`` in the DB so the user's local
clock has no effect — handy when the admin is in Casablanca and the server is
in Helsinki.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.security import require_admin
from app.schemas.ai_logs import (
    AiCostSummary,
    DailyPoint,
    FailureCount,
    ProviderModelBreakdown,
    TopArticle,
    WindowTotals,
)
from app.schemas.auth import AdminUser

router = APIRouter(prefix="/admin/ai-logs", tags=["admin", "ai-logs"])


# --- Helpers -----------------------------------------------------------------


async def _window_totals(session: AsyncSession, *, days: int) -> WindowTotals:
    """Aggregate (calls, cost_usd) over the last N days.

    ``days`` is passed as a bind parameter via ``make_interval`` — no string
    interpolation, no SQL injection surface.
    """
    sql = text(
        """
        SELECT COUNT(*)::int AS calls,
               COALESCE(SUM(cost_usd), 0)::numeric AS cost_usd
        FROM ai_logs
        WHERE success = true
          AND created_at >= NOW() - make_interval(days => :days)
        """
    )
    row = (await session.execute(sql, {"days": days})).one()
    return WindowTotals(calls=int(row.calls), cost_usd=Decimal(str(row.cost_usd)))


async def _month_to_date(session: AsyncSession) -> WindowTotals:
    sql = text(
        """
        SELECT COUNT(*)::int AS calls,
               COALESCE(SUM(cost_usd), 0)::numeric AS cost_usd
        FROM ai_logs
        WHERE success = true
          AND created_at >= date_trunc('month', NOW())
        """
    )
    row = (await session.execute(sql)).one()
    return WindowTotals(calls=int(row.calls), cost_usd=Decimal(str(row.cost_usd)))


async def _by_provider_model(session: AsyncSession) -> list[ProviderModelBreakdown]:
    sql = text(
        """
        SELECT provider, model,
               COUNT(*)::int AS calls,
               COALESCE(SUM(cost_usd), 0)::numeric AS cost_usd
        FROM ai_logs
        WHERE success = true
          AND created_at >= NOW() - INTERVAL '30 days'
        GROUP BY provider, model
        ORDER BY cost_usd DESC
        """
    )
    return [
        ProviderModelBreakdown(
            provider=r.provider,
            model=r.model,
            calls=int(r.calls),
            cost_usd=Decimal(str(r.cost_usd)),
        )
        for r in (await session.execute(sql)).all()
    ]


async def _daily_series(session: AsyncSession) -> list[DailyPoint]:
    """One row per day for the last 14 days. Days with no calls are still
    returned (cost_usd=0, calls=0) so the chart has no holes."""
    sql = text(
        """
        WITH days AS (
            SELECT generate_series(
                (NOW() - INTERVAL '13 days')::date,
                NOW()::date,
                INTERVAL '1 day'
            )::date AS day
        )
        SELECT d.day,
               COALESCE(COUNT(l.id), 0)::int AS calls,
               COALESCE(SUM(l.cost_usd), 0)::numeric AS cost_usd
        FROM days d
        LEFT JOIN ai_logs l
            ON date_trunc('day', l.created_at)::date = d.day
           AND l.success = true
        GROUP BY d.day
        ORDER BY d.day ASC
        """
    )
    return [
        DailyPoint(
            day=r.day if isinstance(r.day, date) else date.fromisoformat(str(r.day)),
            calls=int(r.calls),
            cost_usd=Decimal(str(r.cost_usd)),
        )
        for r in (await session.execute(sql)).all()
    ]


async def _top_articles(session: AsyncSession, *, limit: int = 10) -> list[TopArticle]:
    sql = text(
        """
        SELECT raw_article_id,
               COUNT(*)::int AS calls,
               COALESCE(SUM(cost_usd), 0)::numeric AS cost_usd
        FROM ai_logs
        WHERE success = true
          AND raw_article_id IS NOT NULL
          AND created_at >= NOW() - INTERVAL '30 days'
        GROUP BY raw_article_id
        ORDER BY cost_usd DESC
        LIMIT :limit
        """
    )
    return [
        TopArticle(
            raw_article_id=int(r.raw_article_id),
            calls=int(r.calls),
            cost_usd=Decimal(str(r.cost_usd)),
        )
        for r in (await session.execute(sql, {"limit": limit})).all()
    ]


async def _recent_failures(session: AsyncSession) -> list[FailureCount]:
    sql = text(
        """
        SELECT provider, model, COUNT(*)::int AS failures
        FROM ai_logs
        WHERE success = false
          AND created_at >= NOW() - INTERVAL '7 days'
        GROUP BY provider, model
        ORDER BY failures DESC
        """
    )
    return [
        FailureCount(provider=r.provider, model=r.model, failures=int(r.failures))
        for r in (await session.execute(sql)).all()
    ]


# --- Endpoint ----------------------------------------------------------------


@router.get("/summary", response_model=AiCostSummary)
async def get_cost_summary(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _admin: AdminUser = Depends(require_admin),
) -> dict[str, Any]:
    """All-in-one payload for the admin cost dashboard.

    Six independent queries against ``ai_logs``. The cost is dominated by the
    over-the-wire AI call latency in practice; the DB queries are < 50 ms
    each at the expected row count (~thousands).
    """
    today = await _window_totals(session, days=1)
    last_7_days = await _window_totals(session, days=7)
    month_to_date = await _month_to_date(session)
    by_provider_model = await _by_provider_model(session)
    daily_series = await _daily_series(session)
    top_articles = await _top_articles(session)
    recent_failures = await _recent_failures(session)

    return {
        "today": today,
        "last_7_days": last_7_days,
        "month_to_date": month_to_date,
        "monthly_cap_usd": Decimal(str(settings.ai_monthly_cap_usd)),
        "daily_threshold_usd": Decimal(str(settings.ai_spend_daily_threshold_usd)),
        "by_provider_model": by_provider_model,
        "daily_series": daily_series,
        "top_articles": top_articles,
        "recent_failures": recent_failures,
    }
