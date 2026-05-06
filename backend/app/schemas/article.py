from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArticleAdmin(BaseModel):
    """Compact admin list view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_article_id: int
    slug: str
    title_darija: str
    excerpt_darija: str
    hero_image_url: str | None
    hero_image_alt: str | None
    categories: list[str]
    tags: list[str]
    word_count: int | None
    reading_time_minutes: int | None
    is_published: bool
    published_at: datetime | None
    views_count: int
    created_at: datetime
    updated_at: datetime


class ArticleAdminDetail(ArticleAdmin):
    """Full article including full body (for editor view)."""

    content_darija: str
    meta_title: str | None
    meta_description: str | None


class ArticlePublic(BaseModel):
    """Compact public list view — only fields safe to expose."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title_darija: str
    excerpt_darija: str
    hero_image_url: str | None
    hero_image_alt: str | None
    categories: list[str]
    tags: list[str]
    word_count: int | None
    reading_time_minutes: int | None
    published_at: datetime | None


class ArticlePublicDetail(ArticlePublic):
    """Public single-article view — includes the body."""

    content_darija: str
    meta_title: str | None
    meta_description: str | None


class ArticleUpdate(BaseModel):
    """PATCH body. All fields optional; only provided ones are updated."""

    title_darija: str | None = Field(default=None, min_length=1, max_length=500)
    excerpt_darija: str | None = Field(default=None, min_length=1, max_length=1000)
    content_darija: str | None = Field(default=None, min_length=1)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    meta_title: str | None = Field(default=None, max_length=500)
    meta_description: str | None = Field(default=None, max_length=1000)
    hero_image_alt: str | None = Field(default=None, max_length=500)
    categories: list[str] | None = None
    tags: list[str] | None = None
