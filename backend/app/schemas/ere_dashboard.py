"""Response schemas for the read-only ERE observability dashboard.

All shapes mirror aggregates over the SHADOW-scored ``raw_articles`` subset
(``editorial_score IS NOT NULL``). Nothing here drives ranking, enforcement, or
publication — it is observability only.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class EreOverview(BaseModel):
    """Section 1 — executive cards."""

    total: int
    selected: int
    deferred: int
    selected_pct: float
    deferred_pct: float
    avg_score: float
    max_score: int
    min_score: int
    last_scored: str | None = Field(description="ISO timestamp of the most recent score.")
    model: str = Field(description="Importance model in use, e.g. v1_1.")


class HistogramBin(BaseModel):
    bin: int
    low: int
    high: int
    count: int


class ScoreBucket(BaseModel):
    bucket: str
    count: int


class EreDistribution(BaseModel):
    """Section 2 — score histogram + editorial buckets."""

    histogram: list[HistogramBin]
    buckets: list[ScoreBucket]
    threshold: int


class EreArticle(BaseModel):
    id: int
    title: str
    source: str
    score: int
    decision: str
    category: str
    actors: int
    computed_at: str | None


class EreArticleList(BaseModel):
    """Sections 3/4/7/8 — filtered article list (keyset paginated)."""

    data: list[EreArticle]
    next_cursor: str | None = None


class EreCategory(BaseModel):
    category: str
    count: int
    selected_pct: float
    avg_score: float


class EreCategoryList(BaseModel):
    """Section 5 — per strategic-category analytics."""

    data: list[EreCategory]


class EreSource(BaseModel):
    source: str
    total: int
    selected: int
    deferred: int
    avg_score: float


class EreSourceList(BaseModel):
    """Section 6 — per-source performance."""

    data: list[EreSource]


class PauseFlag(BaseModel):
    active: bool
    reason: str | None = None
    tripped_at: str | None = None
    ttl_seconds: int | None = None


class EreSpendGuard(BaseModel):
    """Section 10 — read-only SpendGuard widgets (no control actions)."""

    today_spend_usd: Decimal
    month_spend_usd: Decimal
    daily_cap_usd: Decimal
    monthly_cap_usd: Decimal
    budget_pause: PauseFlag
    emergency_pause: PauseFlag
    next_auto_resume: str | None = Field(
        default=None,
        description="ISO time the budget pause auto-resumes, or null (running / manual-only).",
    )
