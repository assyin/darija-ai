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


class PipelineStage(BaseModel):
    """Section 1 — one card per pipeline stage."""

    key: str = Field(description="Stable identifier, e.g. 'rss_fetch'.")
    name: str = Field(description="Human-facing stage name.")
    state: HealthState
    description: str = Field(description="One-line explanation of the stage.")


class ActivityItem(BaseModel):
    """Section 2 — last observed activity for a stage."""

    key: str
    label: str
    last_at: str | None = Field(description="ISO timestamp of the last event, or null.")
    age_seconds: int | None = Field(description="Whole seconds since last_at, or null.")
    state: HealthState


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
    pipeline: list[PipelineStage]
    activity: list[ActivityItem]
    spendguard: EreSpendGuard
    queues: QueueCounts
