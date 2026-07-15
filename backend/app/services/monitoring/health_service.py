"""Production Health dashboard — read-only aggregations.

Answers a single question: *is the whole platform working right now?* It reads
the last-activity timestamps of every pipeline stage, the processing-queue
counters, and the SpendGuard state, and derives a simple traffic-light per stage
from the freshness of each signal.

STRICTLY READ-ONLY. Every query is a ``SELECT``; the SpendGuard block reuses the
existing read-only reader (``dashboard_service.ere_spendguard``) and never calls
``allow()`` / ``trip_*`` / ``clear()``. No worker, scheduler, or business state
is touched. Nothing here is scheduled — it runs only when the admin opens the
page.

Health is derived from age thresholds only (no complex computation): a signal is
``healthy`` while fresh, flips to ``warning`` past a soft age, and ``critical``
past a hard age. A signal that never happened (``None``) is reported as
``warning`` (unknown) rather than a false ``critical`` — a fresh/empty database
should not look like an outage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.schemas.ere_dashboard import EreSpendGuard
from app.schemas.health_dashboard import (
    ActivityItem,
    HealthState,
    PipelineStage,
    ProductionHealth,
    QueueCounts,
)
from app.services.editorial.dashboard_service import ere_spendguard

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

# --- Activity definitions -----------------------------------------------------
# (key, section-2 label, pipeline-stage name, description, warn_seconds,
#  crit_seconds). Thresholds are deliberately lenient for manual/optional stages
# (translation, human audit) and tight for the automated heartbeat (RSS fetch).
_HOUR = 3600
_DAY = 24 * _HOUR
_ACTIVITIES: list[tuple[str, str, str, str, int, int]] = [
    (
        "rss_fetch",
        "Last RSS Fetch",
        "RSS Fetch",
        "Ingestion des flux RSS (toutes les 30 min).",
        2 * _HOUR,
        1 * _DAY,
    ),
    (
        "ai_processing",
        "Last AI Processing",
        "AI Processing",
        "Localisation Darija des articles bruts.",
        12 * _HOUR,
        2 * _DAY,
    ),
    (
        "translation",
        "Last Translation",
        "Translation",
        "Traduction française (à la demande).",
        3 * _DAY,
        14 * _DAY,
    ),
    (
        "editorial_ranking",
        "Last Editorial Score",
        "Editorial Ranking",
        "Score éditorial ERE (observation / shadow).",
        1 * _DAY,
        3 * _DAY,
    ),
    (
        "human_audit",
        "Last Human Audit",
        "Human Audit",
        "Verdicts humains KEEP / REJECT.",
        7 * _DAY,
        30 * _DAY,
    ),
    (
        "publication",
        "Last Publication",
        "Publication",
        "Mise en ligne manuelle d'articles.",
        2 * _DAY,
        4 * _DAY,
    ),
]

# One query, one column per signal. Each subselect is a MAX over a table the
# stage writes to; nothing is locked or modified.
_LAST_ACTIVITY_SQL = text(
    """
    SELECT
      (SELECT max(fetched_at) FROM raw_articles)                         AS rss_fetch,
      (SELECT max(created_at) FROM articles)                             AS ai_processing,
      (SELECT max(updated_at) FROM articles WHERE content_fr IS NOT NULL) AS translation,
      (SELECT max(score_breakdown->>'computed_at') FROM raw_articles
         WHERE editorial_score IS NOT NULL)                             AS editorial_ranking,
      (SELECT max(updated_at) FROM editorial_audits)                    AS human_audit,
      (SELECT max(published_at) FROM articles WHERE is_published = true) AS publication
    """
)

_RAW_COUNTS_SQL = text(
    """
    SELECT
      count(*) FILTER (WHERE processing_status = 'pending')::int    AS pending,
      count(*) FILTER (WHERE processing_status = 'processing')::int AS processing,
      count(*) FILTER (WHERE processing_status = 'failed')::int     AS failed,
      count(*) FILTER (WHERE processing_status = 'rejected')::int   AS rejected
    FROM raw_articles
    """
)

_ARTICLE_COUNTS_SQL = text(
    """
    SELECT
      count(*) FILTER (WHERE is_published = false AND deleted_at IS NULL)::int AS draft,
      count(*) FILTER (WHERE is_published = true  AND deleted_at IS NULL)::int AS published
    FROM articles
    """
)


def _state_for_age(age_seconds: int | None, warn: int, crit: int) -> HealthState:
    """Traffic-light from a signal's age. ``None`` (never seen) → warning."""
    if age_seconds is None:
        return "warning"
    if age_seconds >= crit:
        return "critical"
    if age_seconds >= warn:
        return "warning"
    return "healthy"


def _normalize(value: object, now: datetime) -> tuple[str | None, int | None]:
    """Return ``(iso_string, age_seconds)`` for a timestamp or ISO-text value."""
    if value is None:
        return None, None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except ValueError:
            return None, None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    age = int((now - dt).total_seconds())
    return dt.isoformat(), max(0, age)


def _spendguard_state(sg: EreSpendGuard) -> HealthState:
    """Emergency pause → critical, budget pause → warning, else healthy."""
    if sg.emergency_pause.active:
        return "critical"
    if sg.budget_pause.active:
        return "warning"
    return "healthy"


async def production_health(
    session: AsyncSession,
    *,
    redis: Redis,
    daily_cap: float,
    monthly_cap: float,
    now: datetime | None = None,
) -> ProductionHealth:
    """Aggregate the whole-platform health snapshot (read-only)."""
    when = now or datetime.now(UTC)

    activity_row = (await session.execute(_LAST_ACTIVITY_SQL)).one()._mapping
    raw_counts = (await session.execute(_RAW_COUNTS_SQL)).one()._mapping
    article_counts = (await session.execute(_ARTICLE_COUNTS_SQL)).one()._mapping

    # SpendGuard: reuse the existing read-only reader — no duplicated spend logic.
    sg = await ere_spendguard(
        session,
        redis=redis,
        daily_cap=daily_cap,
        monthly_cap=monthly_cap,
        now=when,
    )

    activity: list[ActivityItem] = []
    pipeline: list[PipelineStage] = []
    for key, label, name, description, warn, crit in _ACTIVITIES:
        iso, age = _normalize(activity_row[key], when)
        state = _state_for_age(age, warn, crit)
        activity.append(
            ActivityItem(key=key, label=label, last_at=iso, age_seconds=age, state=state)
        )
        pipeline.append(PipelineStage(key=key, name=name, state=state, description=description))

    # SpendGuard is a pipeline stage too, but its health comes from the pause
    # flags rather than an activity age.
    pipeline.append(
        PipelineStage(
            key="spendguard",
            name="SpendGuard",
            state=_spendguard_state(sg),
            description="Plafond de dépense IA (journalier / mensuel).",
        )
    )

    queues = QueueCounts(
        pending=int(raw_counts["pending"]),
        processing=int(raw_counts["processing"]),
        failed=int(raw_counts["failed"]),
        rejected=int(raw_counts["rejected"]),
        draft=int(article_counts["draft"]),
        published=int(article_counts["published"]),
    )

    return ProductionHealth(
        generated_at=when.isoformat(),
        pipeline=pipeline,
        activity=activity,
        spendguard=sg,
        queues=queues,
    )
