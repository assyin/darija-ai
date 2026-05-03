from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Article(SQLModel, table=True):
    __tablename__ = "articles"
    __table_args__ = (
        Index(
            "idx_articles_categories",
            "categories",
            postgresql_using="gin",
        ),
        Index(
            "idx_articles_tags",
            "tags",
            postgresql_using="gin",
        ),
        Index(
            "idx_articles_is_published_published_at",
            "is_published",
            text("published_at DESC"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    raw_article_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("raw_articles.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    slug: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True)
    )
    title_darija: str = Field(sa_column=Column(Text, nullable=False))
    excerpt_darija: str = Field(sa_column=Column(Text, nullable=False))
    content_darija: str = Field(sa_column=Column(Text, nullable=False))
    meta_title: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    meta_description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    hero_image_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    hero_image_alt: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    categories: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(String),
            nullable=False,
            server_default=text("'{}'::varchar[]"),
        ),
    )
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(String),
            nullable=False,
            server_default=text("'{}'::varchar[]"),
        ),
    )
    reading_time_minutes: int | None = Field(default=None, nullable=True)
    word_count: int | None = Field(default=None, nullable=True)
    is_published: bool = Field(default=False, nullable=False)
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    views_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=_utcnow,
        ),
    )
