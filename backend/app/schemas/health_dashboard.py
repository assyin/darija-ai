"""Response schemas for the read-only Production Health dashboard.

Everything here is OBSERVABILITY ONLY. The dashboard aggregates existing state
(``raw_articles``, ``articles``, ``editorial_audits``, ``ai_logs`` and the
SpendGuard Redis flags) and never drives ingestion, ranking, publication, or any
control action. No field here is ever written back.

The SpendGuard block reuses :class:`app.schemas.ere_dashboard.EreSpendGuard` so
the spend/pause logic is defined in exactly one place.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ere_dashboard import EreSpendGuard

# Traffic-light health state used across every card.
HealthState = Literal["healthy", "warning", "critical"]
# Trend direction for throughput deltas.
TrendDirection = Literal["up", "down", "stable"]


class OverallStatus(BaseModel):
    """Global platform banner — worst-of the pipeline-stage states."""

    state: HealthState
    title: str = Field(description="Production Healthy / Attention Required / Production Incident.")
    detail: str = Field(description="One-line explanation naming the degraded stages.")


class PipelineStage(BaseModel):
    """Section 1 — one card per pipeline stage."""

    key: str = Field(description="Stable identifier, e.g. 'rss_fetch'.")
    name: str = Field(description="Human-facing stage name.")
    state: HealthState
    description: str = Field(description="One-line explanation of the stage.")
    reason: str | None = Field(
        default=None,
        description="Why the stage is degraded (queue rule or pause), when not healthy.",
    )


class FlowNode(BaseModel):
    """Pipeline Flow — one node per step, with its current signal."""

    key: str
    name: str
    value: int
    caption: str = Field(
        description="What the number means, e.g. 'en file' / 'traités aujourd'hui'."
    )
    state: HealthState | None = Field(
        default=None, description="Optional tint for queue-depth nodes."
    )


class ActivityItem(BaseModel):
    """Section 2 — last observed activity for a stage."""

    key: str
    label: str
    last_at: str | None = Field(description="ISO timestamp of the last event, or null.")
    age_seconds: int | None = Field(description="Whole seconds since last_at, or null.")
    state: HealthState


class Trend(BaseModel):
    """Throughput comparison: last 24h vs the previous 24h (honest, timestamp-backed)."""

    key: str
    label: str
    current: int = Field(description="Count in the last 24h window.")
    previous: int = Field(description="Count in the 24-48h window.")
    delta: int
    direction: TrendDirection
    basis: str = Field(description="Timestamp column the trend is derived from.")


class RecentError(BaseModel):
    """A sanitized, structured error surfaced from existing logs (never invented)."""

    stage: str
    provider: str | None = None
    message: str = Field(description="Sanitized, truncated, single-line message. No secrets.")
    at: str = Field(description="ISO timestamp of the error.")


class QueueCounts(BaseModel):
    """Section 4 — raw plumbing counters (read-only)."""

    pending: int
    processing: int
    failed: int
    rejected: int
    draft: int
    published: int


class ProductionHealth(BaseModel):
    """Top-level payload for GET /api/v1/admin/health."""

    generated_at: str = Field(description="ISO timestamp when this snapshot was computed.")
    overall: OverallStatus
    pipeline: list[PipelineStage]
    flow: list[FlowNode]
    activity: list[ActivityItem]
    trends: list[Trend] = Field(description="Honest throughput trends (timestamp-backed only).")
    trends_unavailable: list[str] = Field(
        description="Queue-depth counters with no reliable 24h history (documented limitation).",
    )
    recent_errors: list[RecentError]
    spendguard: EreSpendGuard
    queues: QueueCounts
