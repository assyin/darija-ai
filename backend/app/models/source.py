from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Source(SQLModel, table=True):
    __tablename__ = "sources"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(100), nullable=False))
    rss_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    scraping_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    is_active: bool = Field(default=True, nullable=False)
    needs_html_enrichment: bool = Field(default=False, nullable=False)
    last_fetched_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
