from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RawArticle(SQLModel, table=True):
    __tablename__ = "raw_articles"
    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('pending','processing','translated','published','failed','rejected')",
            name="ck_raw_articles_processing_status",
        ),
        Index(
            "idx_raw_articles_processing_status_fetched_at",
            "processing_status",
            "fetched_at",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    external_url: str = Field(sa_column=Column(Text, nullable=False, unique=True))
    url_hash: str = Field(
        sa_column=Column(String(64), nullable=False, unique=True, index=True)
    )
    original_title: str = Field(sa_column=Column(Text, nullable=False))
    original_content: str = Field(sa_column=Column(Text, nullable=False))
    original_excerpt: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    original_image_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    published_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    fetched_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    processing_status: str = Field(
        default="pending",
        sa_column=Column(String(20), nullable=False, index=True, server_default="pending"),
    )
    rejection_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
