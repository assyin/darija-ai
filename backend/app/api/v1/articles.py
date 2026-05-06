from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.exceptions import ExternalServiceError, NotFoundError
from app.core.logging import get_logger
from app.models.article import Article
from app.schemas.article import (
    ArticleAdmin,
    ArticleAdminDetail,
    ArticlePublic,
    ArticlePublicDetail,
    ArticleUpdate,
)
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
    stmt = (
        stmt.order_by(Article.published_at.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
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
) -> list[Article]:
    """List articles for the admin panel. Filter by published status, paginate."""
    stmt = select(Article).where(Article.deleted_at.is_(None))
    if is_published is not None:
        stmt = stmt.where(Article.is_published.is_(is_published))
    stmt = (
        stmt.order_by(Article.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@admin_router.get("/{article_id}", response_model=ArticleAdminDetail)
async def get_article_admin(
    article_id: int,
    session: AsyncSession = Depends(get_db),
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

    article.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(article)
    return article


@admin_router.post("/{article_id}/publish", response_model=ArticleAdminDetail)
async def publish_article(
    article_id: int,
    session: AsyncSession = Depends(get_db),
) -> Article:
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )
    article.is_published = True
    article.published_at = datetime.now(timezone.utc)
    article.updated_at = article.published_at
    await session.commit()
    await session.refresh(article)
    logger.info(
        "admin.article.published",
        article_id=article.id,
        slug=article.slug,
    )
    return article


@admin_router.post("/{article_id}/unpublish", response_model=ArticleAdminDetail)
async def unpublish_article(
    article_id: int,
    session: AsyncSession = Depends(get_db),
) -> Article:
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )
    article.is_published = False
    # We keep published_at as historical info — only the flag flips.
    article.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(article)
    logger.info(
        "admin.article.unpublished",
        article_id=article.id,
        slug=article.slug,
    )
    return article


@admin_router.post("/{article_id}/regenerate-image", response_model=ArticleAdminDetail)
async def regenerate_article_image(
    article_id: int,
    session: AsyncSession = Depends(get_db),
) -> Article:
    """Re-call ImageGenerator using the article's current hero_image_alt as prompt
    fallback. (We don't currently persist the original image_prompt, so the alt
    text or a derived prompt is used. TODO: persist image_prompt on Article.)"""
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )

    # Best-effort prompt: use stored alt or fall back to the article title.
    prompt = (
        article.hero_image_alt
        or f"Editorial illustration about: {article.title_darija}"
    )

    settings = get_settings()
    if not settings.r2_endpoint_url:
        raise ExternalServiceError(
            "R2 storage is not configured",
            details={"missing": "r2_endpoint_url"},
        )

    provider = ReplicateClient(api_token=settings.replicate_api_token.get_secret_value())
    storage = R2Storage(
        account_id=settings.r2_account_id,
        access_key_id=settings.r2_access_key_id.get_secret_value(),
        secret_access_key=settings.r2_secret_access_key.get_secret_value(),
        bucket_name=settings.r2_bucket_name,
        endpoint_url=settings.r2_endpoint_url,
        public_url=settings.r2_public_url,
    )
    generator = ImageGenerator(provider=provider, storage=storage)
    outcome = await generator.generate_and_upload(
        prompt=prompt, article_slug=article.slug
    )

    article.hero_image_url = outcome.public_url
    article.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(article)
    logger.info(
        "admin.article.image_regenerated",
        article_id=article.id,
        public_url=outcome.public_url,
        cost_usd=str(outcome.cost_usd),
    )
    return article
