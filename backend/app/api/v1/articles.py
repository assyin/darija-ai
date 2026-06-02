from __future__ import annotations

import math
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import AsyncSessionLocal, get_db
from app.core.exceptions import ExternalServiceError, NotFoundError
from app.core.logging import get_logger
from app.core.security import require_admin
from app.models.article import Article
from app.models.raw_article import RawArticle
from app.schemas.article import (
    ArticleAdmin,
    ArticleAdminDetail,
    ArticlePublic,
    ArticlePublicDetail,
    ArticleUpdate,
)
from app.schemas.auth import AdminUser
from app.schemas.proofread import ProofreadRequest, ProofreadResult
from app.services.ai.claude_client import ClaudeClient
from app.services.ai.localizer import Localizer
from app.services.ai.proofreader import Proofreader
from app.services.images.image_generator import ImageGenerator
from app.services.images.r2_storage import R2Storage
from app.services.images.replicate_client import ReplicateClient

logger = get_logger("api.v1.articles")

WORDS_PER_MINUTE = 200

public_router = APIRouter(prefix="/articles", tags=["articles"])


@public_router.get("", response_model=list[ArticlePublic])
async def list_public_articles(
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[Article]:
    """Public list — only published, ordered by published_at DESC."""
    stmt = select(Article).where(
        Article.is_published.is_(True),
        Article.deleted_at.is_(None),
    )
    if category:
        stmt = stmt.where(Article.categories.any(category))
    stmt = stmt.order_by(Article.published_at.desc().nullslast()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@public_router.get("/{slug}", response_model=ArticlePublicDetail)
async def get_public_article(
    slug: str,
    session: AsyncSession = Depends(get_db),
) -> Article:
    stmt = select(Article).where(
        Article.slug == slug,
        Article.is_published.is_(True),
        Article.deleted_at.is_(None),
    )
    article = (await session.execute(stmt)).scalar_one_or_none()
    if article is None:
        raise NotFoundError(
            f"Article '{slug}' not found",
            details={"slug": slug},
        )
    return article


@public_router.get("/categories/{category_slug}", response_model=list[ArticlePublic])
async def list_articles_by_category(
    category_slug: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[Article]:
    stmt = (
        select(Article)
        .where(
            Article.is_published.is_(True),
            Article.deleted_at.is_(None),
            Article.categories.any(category_slug),
        )
        .order_by(Article.published_at.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


admin_router = APIRouter(prefix="/admin/articles", tags=["admin", "articles"])


@admin_router.get("", response_model=list[ArticleAdmin])
async def list_articles_admin(
    is_published: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_admin),
) -> list[Article]:
    """List articles for the admin panel. Filter by published status, paginate."""
    stmt = select(Article).where(Article.deleted_at.is_(None))
    if is_published is not None:
        stmt = stmt.where(Article.is_published.is_(is_published))
    stmt = stmt.order_by(Article.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@admin_router.get("/{article_id}", response_model=ArticleAdminDetail)
async def get_article_admin(
    article_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_admin),
) -> Article:
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )
    return article


@admin_router.patch("/{article_id}", response_model=ArticleAdminDetail)
async def update_article_admin(
    article_id: int,
    update: ArticleUpdate,
    session: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
) -> Article:
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )

    payload = update.model_dump(exclude_unset=True)
    if not payload:
        return article

    for field, value in payload.items():
        setattr(article, field, value)

    # Recompute derived fields when content changes.
    if "content_darija" in payload:
        wc = len(article.content_darija.split())
        article.word_count = wc
        article.reading_time_minutes = max(1, math.ceil(wc / WORDS_PER_MINUTE))

    article.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(article)
    return article


@admin_router.post("/{article_id}/publish", response_model=ArticleAdminDetail)
async def publish_article(
    article_id: int,
    session: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
) -> Article:
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )
    article.is_published = True
    article.published_at = datetime.now(UTC)
    article.updated_at = article.published_at
    await session.commit()
    await session.refresh(article)
    logger.info(
        "admin.article.published",
        article_id=article.id,
        slug=article.slug,
        admin_email=user.email,
    )
    return article


@admin_router.post("/{article_id}/unpublish", response_model=ArticleAdminDetail)
async def unpublish_article(
    article_id: int,
    session: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
) -> Article:
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )
    article.is_published = False
    # We keep published_at as historical info — only the flag flips.
    article.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(article)
    logger.info(
        "admin.article.unpublished",
        article_id=article.id,
        slug=article.slug,
        admin_email=user.email,
    )
    return article


@admin_router.post("/{article_id}/proofread", response_model=ProofreadResult)
async def proofread_article_field(
    article_id: int,
    payload: ProofreadRequest,
    session: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
) -> ProofreadResult:
    """Evaluate an editorial translation snippet and return a score + fix list.

    The text comes from the request body, NOT from the DB, so the admin UI can
    proofread *unsaved drafts* as the editor types. ``article_id`` is used
    only for authorization + audit logging.

    Cached in Redis 24 h by (model, lang, field, sha256(text)) — re-evaluating
    the same text is free.
    """
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )

    settings = get_settings()
    if not settings.openai_api_key:
        raise ExternalServiceError(
            "OpenAI API key not configured",
            details={"setting": "OPENAI_API_KEY"},
        )

    async with _redis_for(settings) as redis_client:
        proofreader = Proofreader(
            api_key=settings.openai_api_key,
            redis_client=redis_client,
            model=settings.proofreader_model,
        )
        result = await proofreader.proofread(
            text=payload.text,
            lang=payload.lang,
            field=payload.field,
        )

    logger.info(
        "admin.article.proofread",
        article_id=article_id,
        field=payload.field,
        lang=payload.lang,
        score=result.score,
        num_suggestions=len(result.suggestions),
        cached=result.cached,
        text_chars=len(payload.text),
        admin_email=user.email,
    )
    return result


@admin_router.post("/{article_id}/regenerate-image", response_model=ArticleAdminDetail)
async def regenerate_article_image(
    article_id: int,
    session: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
) -> Article:
    """Regenerate the article hero image.

    Two-pass flow so the result is actually visible:
      1. Re-run the Localizer on the original raw_article (via Redis cache
         when available — cheap on retries) to derive a *fresh* English
         image_prompt aligned with the current localizer prompt version
         (e.g. v3 = story-driven, category-aware — magazine-cover style,
         no more abstract neural-net wallpaper).
      2. Generate the image with Flux/Replicate and upload it to R2 under
         a UUID-suffixed key (``{slug}-{rev}.{ext}``) so the public URL
         changes. Without this, browsers and Next/Image cache the old URL
         and the admin sees no change even after a successful regen.

    Falls back to ``hero_image_alt`` / ``title_darija`` as the prompt if
    the original ``raw_article`` row is gone (deleted source) or the
    Localizer call fails. Worth fixing the underlying source rather than
    relying on this fallback.
    """
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )

    settings = get_settings()
    if not settings.r2_endpoint_url:
        raise ExternalServiceError(
            "R2 storage is not configured",
            details={"missing": "r2_endpoint_url"},
        )

    # 1) Fresh image_prompt from the source.
    prompt, prompt_source = await _derive_fresh_image_prompt(article, settings)

    # 2) Generate + upload under a cache-busting key so the URL changes.
    revision = uuid.uuid4().hex[:8]
    versioned_slug = f"{article.slug}-{revision}"

    generator = _build_image_generator(settings)
    outcome = await generator.generate_and_upload(
        prompt=prompt,
        article_slug=versioned_slug,
    )

    article.hero_image_url = outcome.public_url
    article.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(article)
    logger.info(
        "admin.article.image_regenerated",
        article_id=article.id,
        public_url=outcome.public_url,
        prompt_source=prompt_source,
        prompt_preview=prompt[:140],
        revision=revision,
        cost_usd=str(outcome.cost_usd),
        admin_email=user.email,
    )
    return article


async def _derive_fresh_image_prompt(article: Article, settings: Settings) -> tuple[str, str]:
    """Return ``(prompt, source_label)``.

    Tries the Localizer first (best quality, current v3 strategy); if the
    raw source is missing or the Localizer raises, falls back to stored
    alt text or the localized title.
    """
    fallback_prompt = (
        article.hero_image_alt or f"Editorial illustration about: {article.title_darija}"
    )
    if article.raw_article_id is None:
        return fallback_prompt, "fallback_no_raw"

    async with _redis_for(settings) as redis_client:
        try:
            async with _session_for_raw() as s:
                raw = await s.get(RawArticle, article.raw_article_id)
                if raw is None:
                    return fallback_prompt, "fallback_raw_deleted"
                title = raw.original_title
                content = raw.original_content
                raw_id = raw.id

            provider = ClaudeClient(settings.anthropic_api_key)
            localizer = Localizer(
                provider=provider,
                redis_client=redis_client,
                prompt_version=settings.localizer_prompt_version,
            )
            localized = await localizer.localize(
                title=title,
                content=content,
                source_name="regen",
                raw_article_id=raw_id or 0,
            )
            return localized.image_prompt, f"localizer:{settings.localizer_prompt_version}"
        except Exception as exc:
            logger.warning(
                "admin.article.image_regen_prompt_fallback",
                article_id=article.id,
                error=f"{exc.__class__.__name__}: {exc}",
            )
            return fallback_prompt, "fallback_localizer_error"


def _build_image_generator(settings: Settings) -> ImageGenerator:
    provider = ReplicateClient(api_token=settings.replicate_api_token.get_secret_value())
    storage = R2Storage(
        account_id=settings.r2_account_id,
        access_key_id=settings.r2_access_key_id.get_secret_value(),
        secret_access_key=settings.r2_secret_access_key.get_secret_value(),
        bucket_name=settings.r2_bucket_name,
        endpoint_url=settings.r2_endpoint_url,
        public_url=settings.r2_public_url,
    )
    return ImageGenerator(provider=provider, storage=storage)


# --- async context managers for one-shot redis + DB usage in regen ---


@asynccontextmanager
async def _redis_for(settings: Settings):  # type: ignore[no-untyped-def]
    client = aioredis.from_url(str(settings.redis_url))
    try:
        yield client
    finally:
        await client.aclose()


@asynccontextmanager
async def _session_for_raw():  # type: ignore[no-untyped-def]
    async with AsyncSessionLocal() as s:
        yield s
