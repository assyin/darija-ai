"""Response schemas for the admin AI cost dashboard.

Used by ``GET /api/v1/admin/ai-logs/summary`` and rendered by the
``/admin/costs`` frontend page. Money is :class:`Decimal` end-to-end —
serialized as a string in JSON to avoid float drift.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class WindowTotals(BaseModel):
    """Total cost + call count over a time window."""

    calls: int = Field(description="Number of successful AI calls in this window.")
    cost_usd: Decimal = Field(description="Sum of cost_usd for the window. May be 0.")


class ProviderModelBreakdown(BaseModel):
    """One row of the per-(provider, model) breakdown."""

    provider: str
    model: str
    calls: int
    cost_usd: Decimal


class DailyPoint(BaseModel):
    """One data point for the cost-over-time chart."""

    day: date
    calls: int
    cost_usd: Decimal


class TopArticle(BaseModel):
    """One row of the "top N most expensive articles" table."""

    raw_article_id: int
    calls: int
    cost_usd: Decimal


class FailureCount(BaseModel):
    """Per-(provider, model) failure counts for the recent past."""

    provider: str
    model: str
    failures: int


class AiCostSummary(BaseModel):
    """Top-level payload for the admin dashboard."""

    today: WindowTotals
    last_7_days: WindowTotals
    month_to_date: WindowTotals
    monthly_cap_usd: Decimal = Field(
        description="The configured monthly cap (CLAUDE.md §1: $50). Used for the progress bar."
    )
    daily_threshold_usd: Decimal = Field(
        description="The configured per-day threshold over which the alert fires (CLAUDE.md §5)."
    )
    by_provider_model: list[ProviderModelBreakdown] = Field(
        description="Aggregates over the last 30 days, sorted by cost desc."
    )
    daily_series: list[DailyPoint] = Field(
        description="One point per day for the last 14 days, oldest first."
    )
    top_articles: list[TopArticle] = Field(
        description="Top 10 most expensive raw_article_ids over the last 30 days."
    )
    recent_failures: list[FailureCount] = Field(
        description="Failure counts grouped by provider/model over the last 7 days."
    )
