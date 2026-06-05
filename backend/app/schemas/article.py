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
    # French summary fields — useful for the admin list to flag which articles
    # already have a FR translation.
    title_fr: str | None = None
    excerpt_fr: str | None = None
    # Auto-flag mode (CLAUDE.md §1 unchanged: hints only, never auto-publish).
    # Populated by the pipeline after the Proofreader runs on the body.
    proofread_score_darija: int | None = None
    proofread_score_fr: int | None = None
    proofread_at: datetime | None = None
    proofread_ready_to_publish: bool = False


class ArticleAdminDetail(ArticleAdmin):
    """Full article including full body (for editor view)."""

    content_darija: str
    meta_title: str | None
    meta_description: str | None
    # Full French content for the editor.
    content_fr: str | None = None
    meta_title_fr: str | None = None
    meta_description_fr: str | None = None


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
    # Exposed for sitemap.xml `<lastmod>` — reflects post-publication edits
    # the editor made via the admin (re-translate, image regen, etc.).
    updated_at: datetime | None = None
    # French variants (nullable). Frontend chooses based on locale, with darija
    # fallback if a FR variant hasn't been authored yet.
    title_fr: str | None = None
    excerpt_fr: str | None = None


class ArticlePublicDetail(ArticlePublic):
    """Public single-article view — includes the body."""

    content_darija: str
    meta_title: str | None
    meta_description: str | None
    content_fr: str | None = None
    meta_title_fr: str | None = None
    meta_description_fr: str | None = None


class BulkProofreadRequest(BaseModel):
    """Body for POST /admin/articles/bulk-evaluate-proofread.

    Defaults target the common case: re-score the drafts that were created
    before the auto-flag pipeline shipped (or that the Proofreader silently
    failed on). The admin can opt to re-score *everything* by flipping the
    flags off.
    """

    only_drafts: bool = True
    only_unevaluated: bool = True


class BulkProofreadResult(BaseModel):
    """Summary returned to the admin after a bulk-evaluate run."""

    evaluated: int = Field(description="Articles that received at least one new score.")
    skipped: int = Field(description="Articles that did not match the filters.")
    failed: int = Field(description="Articles where every Proofreader call errored.")
    ready_after: int = Field(
        description=(
            "Articles flagged 'ready to publish' after this run (cumulative across all drafts)."
        ),
    )
    duration_seconds: float = Field(description="Server-side wall-clock time, for UI sizing.")
    cost_estimate_usd: str = Field(
        description="Best-effort total cost of the run, summed from per-call estimates.",
    )


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
    # French fields — can be set to an empty string to clear, or omitted to leave
    # unchanged (Pydantic's exclude_unset path).
    title_fr: str | None = Field(default=None, max_length=500)
    excerpt_fr: str | None = Field(default=None, max_length=1000)
    content_fr: str | None = Field(default=None)
    meta_title_fr: str | None = Field(default=None, max_length=500)
    meta_description_fr: str | None = Field(default=None, max_length=1000)
