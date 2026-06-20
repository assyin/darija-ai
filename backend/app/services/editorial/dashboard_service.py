"""Read-only aggregates for the ERE observability dashboard.

Every function is a pure read over the SHADOW-scored ``raw_articles`` subset
(``editorial_score IS NOT NULL``) joined to ``sources``, plus ``ai_logs`` /
Redis for the SpendGuard widget. No writes, no ranking, no side effects.

Strategic category is derived from ``score_breakdown.importance_detail``:
  strategic_label != 'none'             -> that label
  strategic_label == 'none' & actors>0  -> 'actors_only'
  else                                  -> 'none'

All SQL is fully literal (no f-string interpolation) with bind parameters.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.schemas.ere_dashboard import (
    EreArticle,
    EreCategory,
    EreDistribution,
    EreOverview,
    EreSource,
    EreSpendGuard,
    HistogramBin,
    PauseFlag,
    ScoreBucket,
)
from app.services.ai.spend_guard import (
    BUDGET_PAUSE_KEY,
    EMERGENCY_PAUSE_KEY,
    LEGACY_PAUSE_KEY,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

IMPORTANCE_MODEL = "v1_1"
THRESHOLD = 55


async def ere_overview(session: AsyncSession) -> EreOverview:
    sql = text(
        """
        SELECT count(*)::int AS total,
               count(*) FILTER (WHERE editorial_decision='selected')::int AS selected,
               count(*) FILTER (WHERE editorial_decision='deferred')::int AS deferred,
               COALESCE(round(avg(editorial_score), 1), 0)::float AS avg_score,
               COALESCE(max(editorial_score), 0)::int AS max_score,
               COALESCE(min(editorial_score), 0)::int AS min_score,
               max(score_breakdown->>'computed_at') AS last_scored
        FROM raw_articles
        WHERE editorial_score IS NOT NULL
        """
    )
    row = (await session.execute(sql)).one()
    total = int(row.total)
    selected = int(row.selected)
    deferred = int(row.deferred)
    return EreOverview(
        total=total,
        selected=selected,
        deferred=deferred,
        selected_pct=round(100.0 * selected / total, 1) if total else 0.0,
        deferred_pct=round(100.0 * deferred / total, 1) if total else 0.0,
        avg_score=float(row.avg_score),
        max_score=int(row.max_score),
        min_score=int(row.min_score),
        last_scored=row.last_scored,
        model=IMPORTANCE_MODEL,
    )


async def ere_distribution(session: AsyncSession) -> EreDistribution:
    hist_sql = text(
        """
        SELECT width_bucket(editorial_score, 0, 100, 20)::int AS bin, count(*)::int AS n
        FROM raw_articles WHERE editorial_score IS NOT NULL
        GROUP BY bin
        """
    )
    counts = {int(r.bin): int(r.n) for r in (await session.execute(hist_sql)).all()}
    # 20 fixed 5-point bins (1..20); width_bucket returns 21 only for score==100.
    histogram: list[HistogramBin] = []
    for b in range(1, 21):
        n = counts.get(b, 0) + (counts.get(21, 0) if b == 20 else 0)
        histogram.append(HistogramBin(bin=b, low=(b - 1) * 5, high=b * 5, count=n))

    bucket_sql = text(
        """
        SELECT CASE
                 WHEN editorial_score<=20 THEN '0-20'
                 WHEN editorial_score<=40 THEN '21-40'
                 WHEN editorial_score<=54 THEN '41-54'
                 WHEN editorial_score<=69 THEN '55-69'
                 WHEN editorial_score<=84 THEN '70-84'
                 ELSE '85-100'
               END AS bucket, count(*)::int AS n
        FROM raw_articles WHERE editorial_score IS NOT NULL
        GROUP BY bucket
        """
    )
    bcounts = {str(r.bucket): int(r.n) for r in (await session.execute(bucket_sql)).all()}
    order = ["0-20", "21-40", "41-54", "55-69", "70-84", "85-100"]
    buckets = [ScoreBucket(bucket=b, count=bcounts.get(b, 0)) for b in order]
    return EreDistribution(histogram=histogram, buckets=buckets, threshold=THRESHOLD)


def _parse_cursor(cursor: str | None) -> tuple[int, int] | None:
    if not cursor:
        return None
    try:
        score_s, id_s = cursor.split(":", 1)
        return int(score_s), int(id_s)
    except (ValueError, AttributeError):
        return None


# Derived category computed once in a CTE; the outer query filters the alias so
# the CASE never has to be repeated (and the SQL stays fully literal).
_ARTICLES_SQL = text(
    """
    WITH scored AS (
      SELECT r.id::int AS id, r.original_title AS title, s.name AS source,
             r.editorial_score::int AS score, r.editorial_decision AS decision,
             CASE
               WHEN (r.score_breakdown->'importance_detail'->>'strategic_label') <> 'none'
                    THEN (r.score_breakdown->'importance_detail'->>'strategic_label')
               WHEN COALESCE((r.score_breakdown->'importance_detail'->>'actors')::int, 0) > 0
                    THEN 'actors_only'
               ELSE 'none'
             END AS category,
             COALESCE((r.score_breakdown->'importance_detail'->>'actors')::int, 0) AS actors,
             (r.score_breakdown->>'computed_at') AS computed_at
      FROM raw_articles r JOIN sources s ON s.id = r.source_id
      WHERE r.editorial_score IS NOT NULL
    )
    SELECT id, title, source, score, decision, category, actors, computed_at
    FROM scored
    WHERE (:decision IS NULL OR decision = :decision)
      AND (:source   IS NULL OR source = :source)
      AND (:category IS NULL OR category = :category)
      AND score BETWEEN :score_min AND :score_max
      AND (:date_from IS NULL OR computed_at::timestamptz >= :date_from::timestamptz)
      AND (:date_to   IS NULL OR computed_at::timestamptz <  :date_to::timestamptz)
      AND (:cur_score IS NULL OR (score, id) < (:cur_score, :cur_id))
    ORDER BY score DESC, id DESC
    LIMIT :limit
    """
)


async def ere_articles(
    session: AsyncSession,
    *,
    decision: str | None = None,
    source: str | None = None,
    category: str | None = None,
    score_min: int = 0,
    score_max: int = 100,
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[EreArticle], str | None]:
    cur = _parse_cursor(cursor)
    params = {
        "decision": decision,
        "source": source,
        "category": category,
        "score_min": score_min,
        "score_max": score_max,
        "date_from": date_from,
        "date_to": date_to,
        "cur_score": cur[0] if cur else None,
        "cur_id": cur[1] if cur else None,
        "limit": limit,
    }
    rows = (await session.execute(_ARTICLES_SQL, params)).all()
    items = [
        EreArticle(
            id=int(r.id),
            title=r.title,
            source=r.source,
            score=int(r.score),
            decision=r.decision,
            category=r.category,
            actors=int(r.actors),
            computed_at=r.computed_at,
        )
        for r in rows
    ]
    next_cursor = f"{items[-1].score}:{items[-1].id}" if len(items) == limit and items else None
    return items, next_cursor


_CATEGORIES_SQL = text(
    """
    WITH scored AS (
      SELECT editorial_decision AS decision, editorial_score AS score,
             CASE
               WHEN (score_breakdown->'importance_detail'->>'strategic_label') <> 'none'
                    THEN (score_breakdown->'importance_detail'->>'strategic_label')
               WHEN COALESCE((score_breakdown->'importance_detail'->>'actors')::int, 0) > 0
                    THEN 'actors_only'
               ELSE 'none'
             END AS category
      FROM raw_articles WHERE editorial_score IS NOT NULL
    )
    SELECT category, count(*)::int AS n,
           round(
             100.0 * count(*) FILTER (WHERE decision='selected') / count(*), 1
           )::float AS sel_pct,
           round(avg(score), 1)::float AS avg_score
    FROM scored GROUP BY category ORDER BY n DESC
    """
)


async def ere_categories(session: AsyncSession) -> list[EreCategory]:
    rows = (await session.execute(_CATEGORIES_SQL)).all()
    return [
        EreCategory(
            category=str(r.category),
            count=int(r.n),
            selected_pct=float(r.sel_pct),
            avg_score=float(r.avg_score),
        )
        for r in rows
    ]


_SOURCES_SQL = text(
    """
    SELECT s.name AS source, count(*)::int AS total,
           count(*) FILTER (WHERE r.editorial_decision='selected')::int AS selected,
           count(*) FILTER (WHERE r.editorial_decision='deferred')::int AS deferred,
           round(avg(r.editorial_score), 1)::float AS avg_score
    FROM raw_articles r JOIN sources s ON s.id = r.source_id
    WHERE r.editorial_score IS NOT NULL
    GROUP BY s.name
    ORDER BY avg_score DESC
    """
)


async def ere_sources(session: AsyncSession) -> list[EreSource]:
    rows = (await session.execute(_SOURCES_SQL)).all()
    return [
        EreSource(
            source=str(r.source),
            total=int(r.total),
            selected=int(r.selected),
            deferred=int(r.deferred),
            avg_score=float(r.avg_score),
        )
        for r in rows
    ]


_TODAY_SPEND_SQL = text(
    "SELECT COALESCE(SUM(cost_usd), 0)::numeric AS c FROM ai_logs "
    "WHERE success = true AND created_at >= date_trunc('day', NOW())"
)
_MONTH_SPEND_SQL = text(
    "SELECT COALESCE(SUM(cost_usd), 0)::numeric AS c FROM ai_logs "
    "WHERE success = true AND created_at >= date_trunc('month', NOW())"
)


def _decode(raw: object) -> str | None:
    if raw is None:
        return None
    return raw.decode() if isinstance(raw, bytes) else str(raw)


def _pause_flag(raw: object, ttl: int | None = None) -> PauseFlag:
    val = _decode(raw)
    if val is None:
        return PauseFlag(active=False)
    reason: str | None = None
    tripped_at: str | None = None
    try:
        rec = json.loads(val)
        reason = rec.get("reason")
        tripped_at = rec.get("tripped_at")
    except (json.JSONDecodeError, TypeError):
        pass
    return PauseFlag(
        active=True,
        reason=reason,
        tripped_at=tripped_at,
        ttl_seconds=ttl if (ttl is not None and ttl > 0) else None,
    )


async def ere_spendguard(
    session: AsyncSession,
    *,
    redis: Redis,
    daily_cap: float,
    monthly_cap: float,
    now: datetime | None = None,
) -> EreSpendGuard:
    when = now or datetime.now(UTC)
    today = Decimal(str((await session.execute(_TODAY_SPEND_SQL)).one().c))
    month = Decimal(str((await session.execute(_MONTH_SPEND_SQL)).one().c))

    budget_raw = await redis.get(BUDGET_PAUSE_KEY)
    budget_ttl = await redis.ttl(BUDGET_PAUSE_KEY) if budget_raw is not None else None
    budget = _pause_flag(budget_raw, budget_ttl)

    emer_raw = await redis.get(EMERGENCY_PAUSE_KEY)
    if emer_raw is None:
        emer_raw = await redis.get(LEGACY_PAUSE_KEY)  # legacy honored as emergency
    emergency = _pause_flag(emer_raw)

    next_resume: str | None = None
    if budget.active and not emergency.active and budget.ttl_seconds:
        next_resume = (when + timedelta(seconds=budget.ttl_seconds)).isoformat()

    return EreSpendGuard(
        today_spend_usd=today,
        month_spend_usd=month,
        daily_cap_usd=Decimal(str(daily_cap)),
        monthly_cap_usd=Decimal(str(monthly_cap)),
        budget_pause=budget,
        emergency_pause=emergency,
        next_auto_resume=next_resume,
    )
