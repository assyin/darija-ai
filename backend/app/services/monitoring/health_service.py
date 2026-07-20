"""Production Health dashboard — read-only aggregations.

Answers a single question: *is the whole platform working right now?* It reads
the last-activity timestamps of every pipeline stage, the processing-queue
counters, honest throughput trends, the latest structured error, and the
SpendGuard state, then derives a simple traffic-light per stage and a global
banner.

STRICTLY READ-ONLY. Every query is a ``SELECT``; the SpendGuard block reuses the
existing read-only reader (``dashboard_service.ere_spendguard``) and never calls
``allow()`` / ``trip_*`` / ``clear()``. No worker, scheduler, or business state
is touched. Nothing here is scheduled — it runs only when the admin opens the
page.

Stage health is the WORST of two signals:
  * activity-age  — how fresh the stage's last event is (time-based), and
  * queue-health  — whether the queue itself is backed up (count/stale-based).
A signal that never happened (``None``) is reported as ``warning`` (unknown)
rather than a false ``critical`` — a fresh/empty database is not an outage.

Data-source honesty (P2-01B): queue *depths* (pending/processing/failed/
rejected/draft) have no status-change history in the schema, so a truthful
"24h ago" value cannot be derived without a new snapshot table. We therefore
only publish trends for timestamp-backed *throughput* (fetched / processed /
published / audited) and list the depth counters as unavailable rather than
inventing a misleading delta.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.schemas.ere_dashboard import EreSpendGuard
from app.schemas.health_dashboard import (
    ActivityItem,
    FlowNode,
    HealthState,
    OverallStatus,
    PipelineStage,
    ProductionHealth,
    QueueCounts,
    RecentError,
    Trend,
    TrendDirection,
)
from app.services.editorial.dashboard_service import ere_spendguard

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

# ==========================================================================
# THRESHOLDS — the one documented place to tune dashboard health rules.
# Changing these changes ONLY what the dashboard reports; it never changes any
# actual processing behaviour.
# ==========================================================================

# Activity-age thresholds (warn_seconds, crit_seconds) per stage. Lenient for
# manual/optional stages (translation, human audit), tight for the automated
# RSS heartbeat.
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

# Queue-health thresholds. A backed-up or stuck queue degrades the AI Processing
# stage even when its last-activity age still looks fresh.
PENDING_WARN, PENDING_CRIT = 500, 1000
FAILED_WARN, FAILED_CRIT = 20, 100
STALE_PROCESSING_WARN_S, STALE_PROCESSING_CRIT_S = 1 * _DAY, 5 * _DAY

# ==========================================================================
# SQL — every statement is a read-only SELECT.
# ==========================================================================

_LAST_ACTIVITY_SQL = text(
    """
    SELECT
      (SELECT max(fetched_at) FROM raw_articles)                          AS rss_fetch,
      (SELECT max(created_at) FROM articles)                              AS ai_processing,
      (SELECT max(updated_at) FROM articles WHERE content_fr IS NOT NULL) AS translation,
      (SELECT max(score_breakdown->>'computed_at') FROM raw_articles
         WHERE editorial_score IS NOT NULL)                              AS editorial_ranking,
      (SELECT max(updated_at) FROM editorial_audits)                     AS human_audit,
      (SELECT max(published_at) FROM articles WHERE is_published = true)  AS publication
    """
)

_QUEUE_SQL = text(
    """
    SELECT
      count(*) FILTER (WHERE processing_status = 'pending')::int    AS pending,
      count(*) FILTER (WHERE processing_status = 'processing')::int AS processing,
      count(*) FILTER (WHERE processing_status = 'failed')::int     AS failed,
      count(*) FILTER (WHERE processing_status = 'rejected')::int   AS rejected,
      (SELECT count(*) FILTER (WHERE is_published = false AND deleted_at IS NULL)
         FROM articles)::int AS draft,
      (SELECT count(*) FILTER (WHERE is_published = true AND deleted_at IS NULL)
         FROM articles)::int AS published,
      min(fetched_at) FILTER (WHERE processing_status = 'processing') AS oldest_processing
    FROM raw_articles
    """
)

# Flow throughput: mix of "today" throughput and current queue depths, each node
# self-describing via its caption so nothing is silently conflated.
_FLOW_SQL = text(
    """
    SELECT
      (SELECT count(*) FROM raw_articles
         WHERE fetched_at >= date_trunc('day', now()))::int AS fetched_today,
      (SELECT count(*) FROM articles
         WHERE created_at >= date_trunc('day', now()))::int AS processed_today,
      (SELECT count(*) FROM articles WHERE content_fr IS NOT NULL)::int AS translated_total,
      (SELECT count(*) FROM raw_articles WHERE editorial_score IS NOT NULL)::int AS scored_total,
      (SELECT count(*) FROM editorial_audits
         WHERE created_at >= date_trunc('day', now()))::int AS audited_today,
      (SELECT count(*) FROM articles
         WHERE is_published = true AND published_at >= date_trunc('day', now()))::int
         AS published_today
    """
)

# Honest throughput trends: last-24h vs previous-24h, bound to the caller's clock
# so the window is deterministic and testable.
_TREND_SQL = text(
    """
    SELECT
      (SELECT count(*) FROM raw_articles
         WHERE fetched_at >= :w24 AND fetched_at < :w0)::int AS fetched_cur,
      (SELECT count(*) FROM raw_articles
         WHERE fetched_at >= :w48 AND fetched_at < :w24)::int AS fetched_prev,
      (SELECT count(*) FROM articles
         WHERE created_at >= :w24 AND created_at < :w0)::int AS processed_cur,
      (SELECT count(*) FROM articles
         WHERE created_at >= :w48 AND created_at < :w24)::int AS processed_prev,
      (SELECT count(*) FROM articles
         WHERE is_published = true AND published_at >= :w24 AND published_at < :w0)::int
         AS published_cur,
      (SELECT count(*) FROM articles
         WHERE is_published = true AND published_at >= :w48 AND published_at < :w24)::int
         AS published_prev,
      (SELECT count(*) FROM editorial_audits
         WHERE created_at >= :w24 AND created_at < :w0)::int AS audited_cur,
      (SELECT count(*) FROM editorial_audits
         WHERE created_at >= :w48 AND created_at < :w24)::int AS audited_prev
    """
)

_LAST_AI_ERROR_SQL = text(
    """
    SELECT provider, model, error, created_at
    FROM ai_logs
    WHERE success = false AND error IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 1
    """
)

# Queue-depth counters with no status-change history → no honest 24h delta.
_TRENDS_UNAVAILABLE = ["pending", "processing", "failed", "rejected", "draft"]

# ==========================================================================
# Pure helpers (unit-tested directly).
# ==========================================================================

_STATE_RANK: dict[HealthState, int] = {"healthy": 0, "warning": 1, "critical": 2}
_RANK_STATE: dict[int, HealthState] = {0: "healthy", 1: "warning", 2: "critical"}


def _worst(states: list[HealthState]) -> HealthState:
    """Return the most severe of the given states (healthy < warning < critical)."""
    if not states:
        return "healthy"
    return _RANK_STATE[max(_STATE_RANK[s] for s in states)]


def _state_for_age(age_seconds: int | None, warn: int, crit: int) -> HealthState:
    """Traffic-light from a signal's age. ``None`` (never seen) → warning."""
    if age_seconds is None:
        return "warning"
    if age_seconds >= crit:
        return "critical"
    if age_seconds >= warn:
        return "warning"
    return "healthy"


def queue_state(
    pending: int, failed: int, stale_processing_seconds: int | None
) -> tuple[HealthState, str | None]:
    """Queue-health from depth + staleness thresholds. Returns (state, reason).

    ``reason`` names the worst rule that fired, or ``None`` when healthy.
    """
    candidates: list[tuple[HealthState, str]] = []
    if pending >= PENDING_CRIT:
        candidates.append(("critical", f"File d'attente critique : {pending} en attente."))
    elif pending >= PENDING_WARN:
        candidates.append(("warning", f"File d'attente élevée : {pending} en attente."))
    if failed >= FAILED_CRIT:
        candidates.append(("critical", f"Échecs critiques : {failed} en échec."))
    elif failed >= FAILED_WARN:
        candidates.append(("warning", f"Échecs élevés : {failed} en échec."))
    if stale_processing_seconds is not None:
        if stale_processing_seconds >= STALE_PROCESSING_CRIT_S:
            days = stale_processing_seconds // _DAY
            candidates.append(("critical", f"Traitement bloqué depuis ~{days} j."))
        elif stale_processing_seconds >= STALE_PROCESSING_WARN_S:
            hours = stale_processing_seconds // _HOUR
            candidates.append(("warning", f"Traitement lent : bloqué depuis ~{hours} h."))
    if not candidates:
        return "healthy", None
    worst = _worst([s for s, _ in candidates])
    reason = next(r for s, r in candidates if s == worst)
    return worst, reason


def overall_status(stages: list[PipelineStage]) -> OverallStatus:
    """Global banner from the worst pipeline-stage state."""
    state = _worst([s.state for s in stages])
    if state == "critical":
        title = "Production Incident"
        names = [s.name for s in stages if s.state == "critical"]
        detail = "Étape(s) critique(s) : " + ", ".join(names) + "."
    elif state == "warning":
        title = "Attention Required"
        names = [s.name for s in stages if s.state == "warning"]
        detail = "Attention sur : " + ", ".join(names) + "."
    else:
        title = "Production Healthy"
        detail = "Toutes les étapes du pipeline sont saines."
    return OverallStatus(state=state, title=title, detail=detail)


def trend_direction(delta: int) -> TrendDirection:
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "stable"


# Redact anything that looks like a secret before showing an error message.
_REDACT = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"sk-[a-z0-9\-_]{6,}",
        r"r8_[a-z0-9]{6,}",
        r"bearer\s+\S+",
        r"AKIA[0-9A-Z]{16}",
        r"(?:api[_-]?key|token|secret|password|authorization)\s*[=:]\s*\S+",
        r"\b[0-9a-f]{32,}\b",
    )
]


def sanitize_error(message: str | None) -> str:
    """First line only, secrets redacted, truncated. Never leaks tokens/traces."""
    if not message:
        return ""
    first = message.splitlines()[0].strip()
    for rx in _REDACT:
        first = rx.sub("***", first)
    return first[:200]


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


def _spendguard_state(sg: EreSpendGuard) -> tuple[HealthState, str | None]:
    if sg.emergency_pause.active:
        return "critical", f"Pause d'urgence : {sg.emergency_pause.reason or 'manuelle'}."
    if sg.budget_pause.active:
        return "warning", f"Pause budget : {sg.budget_pause.reason or 'plafond journalier'}."
    return "healthy", None


# ==========================================================================
# Aggregator
# ==========================================================================


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
    q = (await session.execute(_QUEUE_SQL)).one()._mapping
    flow_row = (await session.execute(_FLOW_SQL)).one()._mapping
    trend_row = (
        (
            await session.execute(
                _TREND_SQL,
                {
                    "w0": when,
                    "w24": when - timedelta(hours=24),
                    "w48": when - timedelta(hours=48),
                },
            )
        )
        .one()
        ._mapping
    )
    err_row = (await session.execute(_LAST_AI_ERROR_SQL)).one_or_none()

    sg = await ere_spendguard(
        session, redis=redis, daily_cap=daily_cap, monthly_cap=monthly_cap, now=when
    )

    queues = QueueCounts(
        pending=int(q["pending"]),
        processing=int(q["processing"]),
        failed=int(q["failed"]),
        rejected=int(q["rejected"]),
        draft=int(q["draft"]),
        published=int(q["published"]),
    )

    # Queue-health (degrades AI Processing) — stale age proxied by the oldest
    # still-'processing' row's fetch time (no status-change timestamp exists).
    _, stale_age = _normalize(q["oldest_processing"], when)
    q_state, q_reason = queue_state(queues.pending, queues.failed, stale_age)

    # --- Pipeline stages: worst of activity-age and (for AI Processing) queue ---
    activity: list[ActivityItem] = []
    pipeline: list[PipelineStage] = []
    for key, label, name, description, warn, crit in _ACTIVITIES:
        iso, age = _normalize(activity_row[key], when)
        age_state = _state_for_age(age, warn, crit)
        activity.append(
            ActivityItem(key=key, label=label, last_at=iso, age_seconds=age, state=age_state)
        )
        if key == "ai_processing":
            state = _worst([age_state, q_state])
            reason = q_reason if state == q_state and q_reason else None
        else:
            state = age_state
            reason = None
        pipeline.append(
            PipelineStage(key=key, name=name, state=state, description=description, reason=reason)
        )

    sg_state, sg_reason = _spendguard_state(sg)
    pipeline.append(
        PipelineStage(
            key="spendguard",
            name="SpendGuard",
            state=sg_state,
            description="Plafond de dépense IA (journalier / mensuel).",
            reason=sg_reason,
        )
    )

    # --- Pipeline flow (self-describing captions) ---
    pending_flow_state: HealthState | None = (
        "critical"
        if queues.pending >= PENDING_CRIT
        else "warning"
        if queues.pending >= PENDING_WARN
        else None
    )
    flow = [
        FlowNode(
            key="rss_fetch",
            name="RSS Fetch",
            value=int(flow_row["fetched_today"]),
            caption="récupérés aujourd'hui",
        ),
        FlowNode(
            key="pending",
            name="Pending",
            value=queues.pending,
            caption="en file",
            state=pending_flow_state,
        ),
        FlowNode(
            key="ai_processing",
            name="AI Processing",
            value=int(flow_row["processed_today"]),
            caption="traités aujourd'hui",
        ),
        FlowNode(
            key="translation",
            name="Translation",
            value=int(flow_row["translated_total"]),
            caption="traduits (total)",
        ),
        FlowNode(
            key="editorial_ranking",
            name="Editorial Ranking",
            value=int(flow_row["scored_total"]),
            caption="scorés (total)",
        ),
        FlowNode(
            key="human_audit",
            name="Human Audit",
            value=int(flow_row["audited_today"]),
            caption="audités aujourd'hui",
        ),
        FlowNode(key="draft", name="Draft", value=queues.draft, caption="en file"),
        FlowNode(
            key="published",
            name="Published",
            value=int(flow_row["published_today"]),
            caption="publiés aujourd'hui",
        ),
    ]

    # --- Honest throughput trends (timestamp-backed only) ---
    def _trend(key: str, label: str, basis: str) -> Trend:
        cur = int(trend_row[f"{key}_cur"])
        prev = int(trend_row[f"{key}_prev"])
        delta = cur - prev
        return Trend(
            key=key,
            label=label,
            current=cur,
            previous=prev,
            delta=delta,
            direction=trend_direction(delta),
            basis=basis,
        )

    trends = [
        _trend("fetched", "Récupérés (RSS)", "raw_articles.fetched_at"),
        _trend("processed", "Traités (IA)", "articles.created_at"),
        _trend("published", "Publiés", "articles.published_at"),
        _trend("audited", "Audités", "editorial_audits.created_at"),
    ]

    # --- Recent error (reliable structured source: ai_logs only) ---
    recent_errors: list[RecentError] = []
    if err_row is not None:
        m = err_row._mapping
        recent_errors.append(
            RecentError(
                stage="AI Processing",
                provider=str(m["provider"]) if m["provider"] is not None else None,
                message=sanitize_error(m["error"]),
                at=(m["created_at"].isoformat() if m["created_at"] is not None else ""),
            )
        )

    stages_for_banner = pipeline
    return ProductionHealth(
        generated_at=when.isoformat(),
        overall=overall_status(stages_for_banner),
        pipeline=pipeline,
        flow=flow,
        activity=activity,
        trends=trends,
        trends_unavailable=list(_TRENDS_UNAVAILABLE),
        recent_errors=recent_errors,
        spendguard=sg,
        queues=queues,
    )
