from __future__ import annotations

import asyncio
import math
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.core.config import Settings, get_settings
from app.core.db import AsyncSessionLocal, get_db
from app.core.exceptions import ExternalServiceError, NotFoundError
from app.core.logging import get_logger
from app.core.security import require_admin
from app.models.article import Article
from app.models.raw_article import RawArticle
from app.schemas.article import (
    AdminArticlesListResponse,
    ArticleAdminDetail,
    ArticlePublic,
    ArticlePublicDetail,
    ArticleUpdate,
    BulkProofreadRequest,
    BulkProofreadResult,
)
from app.schemas.auth import AdminUser
from app.schemas.proofread import ProofreadRequest, ProofreadResult
from app.services.ai.ai_logging import LoggingLLMProvider
from app.services.ai.claude_client import ClaudeClient
from app.services.ai.localizer import Localizer
from app.services.ai.proofreader import Proofreader
from app.services.ai.translator import Translator
from app.services.articles.related import compute_related
from app.services.external.indexnow import notify as indexnow_notify
from app.services.images.image_generator import ImageGenerator
from app.services.images.r2_storage import R2Storage
from app.services.images.replicate_client import ReplicateClient

logger = get_logger("api.v1.articles")

WORDS_PER_MINUTE = 200

public_router = APIRouter(prefix="/articles", tags=["articles"])


@public_router.get("", response_model=list[ArticlePublic])
async def list_public_articles(
    category: str | None = Query(default=None),
    lang: str | None = Query(
        default=None,
        description="When 'fr', restrict to articles that have a French "
        "translation (title_fr is non-empty). Default returns everything.",
    ),
    # Cap raised from 100 → 500 so the public sitemap can fetch the full
    # published catalogue in one round-trip (Google sitemap convention is one
    # URL per row, no pagination). Editorial volume is ~50; 500 leaves a
    # comfortable runway before we need to switch to a paginated index.
    limit: int = Query(default=20, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[Article]:
    """Public list — only published, ordered by published_at DESC.

    Pass ``lang=fr`` to limit the listing to articles that have been
    translated to French (used by the /fr/articles page so the FR locale
    never shows Darija-only items in its index).
    """
    stmt = select(Article).where(
        Article.is_published.is_(True),
        Article.deleted_at.is_(None),
    )
    if category:
        stmt = stmt.where(Article.categories.any(category))
    if lang == "fr":
        stmt = stmt.where(
            Article.title_fr.is_not(None),  # type: ignore[union-attr]
            Article.title_fr != "",  # type: ignore[arg-type]
        )
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


@public_router.get("/{slug}/related", response_model=list[ArticlePublic])
async def get_related_articles(
    slug: str,
    lang: str | None = Query(
        default=None,
        description="When 'fr', exclude articles that don't have a French translation.",
    ),
    limit: int = Query(default=4, ge=1, le=5),
    session: AsyncSession = Depends(get_db),
) -> list[Article]:
    """Semantic related-articles rail powering the bottom of every article page.

    Ranks the corpus by weighted overlap of `categories` (x4) + `tags` (x2)
    + a freshness bonus (+1 if published in the last 30 days). Falls back
    to the most-recent publications when the source has no shared signal
    with anything else (niche-tag articles). See
    ``services/articles/related.py`` for the full design.

    Returns an empty list when the source slug is not a published article —
    the frontend renders the rail conditionally on length anyway.
    """
    # Confirm source exists + is public; we only need its slug for the
    # ranker, but a 404 here is cheaper than a silent empty rail.
    source = (
        await session.execute(
            select(Article).where(
                Article.slug == slug,
                Article.is_published.is_(True),
                Article.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if source is None:
        # Mirror the public /articles/{slug} behaviour — unknown slug = 404.
        raise NotFoundError(
            f"Article '{slug}' not found",
            details={"slug": slug},
        )

    return await compute_related(
        session,
        source_slug=slug,
        lang=lang,
        limit=limit,
    )


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


@admin_router.get("", response_model=AdminArticlesListResponse)
async def list_articles_admin(
    is_published: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_admin),
) -> dict[str, Any]:
    """List articles for the admin panel + global counts for the filter badges.

    The `items` array honours `is_published`, `limit`, `offset` so the UI list
    stays paginated. The `counts` block is computed against the whole live
    catalogue (deleted_at IS NULL) and ignores both the pagination AND the
    `is_published` filter — the four filter tabs must always show their true
    totals, even when the currently selected slice is all drafts or all
    published.

    The counts query is a single FILTER aggregate scan on the existing
    `idx_articles_is_published_published_at` index — measured at ~3 ms on the
    current ~200-row table; comfortably under the per-request budget even at
    10x the catalogue size.
    """
    # Items: respects filter + pagination, same SELECT as before.
    items_stmt = select(Article).where(Article.deleted_at.is_(None))
    if is_published is not None:
        items_stmt = items_stmt.where(Article.is_published.is_(is_published))
    items_stmt = items_stmt.order_by(Article.created_at.desc()).limit(limit).offset(offset)
    items_result = await session.execute(items_stmt)
    items = list(items_result.scalars().all())

    # Counts: ignores pagination AND the is_published filter — the four
    # category totals must always reflect the full live catalogue.
    counts_stmt = select(
        func.count().label("all"),
        func.count().filter(col(Article.is_published).is_(False)).label("drafts"),
        func.count()
        .filter(
            col(Article.is_published).is_(False),
            col(Article.proofread_ready_to_publish).is_(True),
        )
        .label("ready"),
        func.count().filter(col(Article.is_published).is_(True)).label("published"),
    ).where(Article.deleted_at.is_(None))
    counts_row = (await session.execute(counts_stmt)).one()

    return {
        "items": items,
        "counts": {
            "all": int(counts_row.all),
            "drafts": int(counts_row.drafts),
            "ready": int(counts_row.ready),
            "published": int(counts_row.published),
        },
    }


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


# Per-call cost estimate for gpt-4o-mini Proofreader runs. The real cost is
# attributed in ai_logs (PR #22) at the actual token usage; this estimate is
# only used to size the bulk-evaluate summary the admin sees.
_PROOFREAD_CALL_COST_USD = Decimal("0.0008")

# Bound concurrency so we don't burst into OpenAI rate limits. Five articles
# = up to 10 concurrent Proofreader calls (Darija + FR), which stays well
# inside the gpt-4o-mini RPM budget while finishing 53 drafts in ~30-50 s.
_BULK_PROOFREAD_CONCURRENCY = 5


@admin_router.post(
    "/bulk-evaluate-proofread",
    response_model=BulkProofreadResult,
)
async def bulk_evaluate_proofread(
    payload: BulkProofreadRequest,
    session: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
) -> BulkProofreadResult:
    """Run the AI Proofreader retroactively on already-persisted articles.

    Default filters target the common case introduced when PR #25 added the
    auto-flag pipeline: drafts created before that shipped have no scores
    yet. This endpoint scores them in one shot so the editor can use the
    "Prêts à publier" filter on the existing backlog.

    Concurrency is bounded by ``_BULK_PROOFREAD_CONCURRENCY`` to avoid
    bursting into OpenAI rate limits. Each article's DB update happens in
    its own session so concurrent successes don't contend.

    Fail-soft per-article: a Proofreader exception on one article does NOT
    abort the run; it counts toward ``failed`` in the summary.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise ExternalServiceError(
            "OpenAI API key not configured",
            details={"setting": "OPENAI_API_KEY"},
        )

    stmt = select(Article).where(Article.deleted_at.is_(None))
    if payload.only_drafts:
        stmt = stmt.where(Article.is_published.is_(False))
    if payload.only_unevaluated:
        stmt = stmt.where(col(Article.proofread_at).is_(None))
    stmt = stmt.order_by(Article.created_at.asc())
    targets = list((await session.execute(stmt)).scalars().all())

    if not targets:
        return BulkProofreadResult(
            evaluated=0,
            skipped=0,
            failed=0,
            ready_after=await _count_ready_drafts(session),
            duration_seconds=0.0,
            cost_estimate_usd=str(Decimal("0")),
        )

    logger.info(
        "admin.articles.bulk_proofread.start",
        admin_email=user.email,
        target_count=len(targets),
        only_drafts=payload.only_drafts,
        only_unevaluated=payload.only_unevaluated,
    )

    threshold = settings.proofread_publish_ready_threshold
    naturalness_floor = settings.proofread_naturalness_floor
    semaphore = asyncio.Semaphore(_BULK_PROOFREAD_CONCURRENCY)
    start = time.perf_counter()

    async with _redis_for(settings) as redis_client:
        proofreader = Proofreader(
            api_key=settings.openai_api_key,
            redis_client=redis_client,
            model=settings.proofreader_model,
        )

        async def _process(article_id: int) -> tuple[bool, bool, int]:
            """Returns (evaluated, failed_both, successful_call_count)."""
            async with semaphore:
                return await _proofread_one_article(
                    article_id=article_id,
                    proofreader=proofreader,
                    threshold=threshold,
                    naturalness_floor=naturalness_floor,
                )

        results = await asyncio.gather(
            *(_process(int(a.id)) for a in targets if a.id is not None),
            return_exceptions=False,
        )

    evaluated = sum(1 for evaluated_, _, _ in results if evaluated_)
    failed = sum(1 for _, failed_both, _ in results if failed_both)
    successful_calls = sum(calls for _, _, calls in results)
    cost_estimate = _PROOFREAD_CALL_COST_USD * successful_calls
    duration_seconds = round(time.perf_counter() - start, 2)
    ready_after = await _count_ready_drafts(session)

    logger.info(
        "admin.articles.bulk_proofread.completed",
        admin_email=user.email,
        evaluated=evaluated,
        failed=failed,
        ready_after=ready_after,
        successful_calls=successful_calls,
        cost_estimate_usd=str(cost_estimate),
        duration_seconds=duration_seconds,
    )

    return BulkProofreadResult(
        evaluated=evaluated,
        skipped=0,
        failed=failed,
        ready_after=ready_after,
        duration_seconds=duration_seconds,
        cost_estimate_usd=str(cost_estimate),
    )


async def _count_ready_drafts(session: AsyncSession) -> int:
    """Count drafts currently flagged ready_to_publish — for the summary card."""
    stmt = (
        select(Article)
        .where(Article.deleted_at.is_(None))
        .where(Article.is_published.is_(False))
        .where(Article.proofread_ready_to_publish.is_(True))
    )
    return len(list((await session.execute(stmt)).scalars().all()))


async def _proofread_one_article(
    *,
    article_id: int,
    proofreader: Proofreader,
    threshold: int,
    naturalness_floor: int,
) -> tuple[bool, bool, int]:
    """Score one article's body in each populated language; update the row.

    Returns ``(evaluated, failed_both, successful_calls)`` where:

    - ``evaluated`` — at least one score landed.
    - ``failed_both`` — every attempted call errored (counted toward
      ``failed`` in the summary).
    - ``successful_calls`` — for cost attribution in the summary.

    Each call is logged to ``ai_logs`` inside ``Proofreader.proofread`` —
    the cost dashboard ``/admin/costs`` shows the bulk run automatically.
    """
    async with AsyncSessionLocal() as own_session:
        article = await own_session.get(Article, article_id)
        if article is None or article.deleted_at is not None:
            return False, False, 0

        score_darija: int | None = None
        score_fr: int | None = None
        nat_darija: int | None = None
        nat_fr: int | None = None
        successful_calls = 0
        attempted_calls = 0

        try:
            attempted_calls += 1
            result = await proofreader.proofread(
                text=article.content_darija,
                lang="darija",
                field="body",
                raw_article_id=article.raw_article_id,
            )
            score_darija = result.score
            nat_darija = result.naturalness_score
            successful_calls += 1
        except Exception as exc:
            logger.warning(
                "admin.articles.bulk_proofread.darija_failed_soft",
                article_id=article_id,
                error=str(exc),
                error_type=exc.__class__.__name__,
            )

        if article.content_fr:
            try:
                attempted_calls += 1
                result_fr = await proofreader.proofread(
                    text=article.content_fr,
                    lang="french",
                    field="body",
                    raw_article_id=article.raw_article_id,
                )
                score_fr = result_fr.score
                nat_fr = result_fr.naturalness_score
                successful_calls += 1
            except Exception as exc:
                logger.warning(
                    "admin.articles.bulk_proofread.fr_failed_soft",
                    article_id=article_id,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                )

        evaluated = score_darija is not None or score_fr is not None
        failed_both = attempted_calls > 0 and not evaluated
        if not evaluated:
            return False, failed_both, successful_calls

        # Same readiness rule as the pipeline: every populated language must
        # clear BOTH the headline threshold AND the naturalness floor. A
        # missing FR is not blocking; a missing naturalness sub-score is
        # treated as "unknown, not blocking" so legacy cached entries are
        # not penalized.
        darija_passes = (
            score_darija is not None
            and score_darija >= threshold
            and (nat_darija is None or nat_darija >= naturalness_floor)
        )
        fr_passes = score_fr is None or (
            score_fr >= threshold and (nat_fr is None or nat_fr >= naturalness_floor)
        )
        ready = darija_passes and fr_passes

        article.proofread_score_darija = score_darija
        article.proofread_score_fr = score_fr
        article.proofread_at = datetime.now(UTC)
        article.proofread_ready_to_publish = ready
        article.updated_at = datetime.now(UTC)
        await own_session.commit()
        return True, False, successful_calls


@admin_router.post("/{article_id}/publish", response_model=ArticleAdminDetail)
async def publish_article(
    article_id: int,
    background_tasks: BackgroundTasks,
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

    # IndexNow: notify Bing/Yandex/etc as soon as the row is committed. Both
    # AR (default locale, no prefix) and FR (when a translation exists) URLs
    # ride in the same call so the editor doesn't pay two RTTs.
    # BackgroundTasks runs after the HTTP response is sent — publish stays
    # snappy and a slow IndexNow can't keep the admin tab spinning.
    settings = get_settings()
    site_url = settings.public_site_url
    url_list = [f"{site_url.rstrip('/')}/articles/{article.slug}"]
    if article.title_fr:
        url_list.append(f"{site_url.rstrip('/')}/fr/articles/{article.slug}")
    background_tasks.add_task(
        indexnow_notify,
        urls=url_list,
        api_key=settings.indexnow_api_key,
        site_url=site_url,
    )

    logger.info(
        "admin.article.published",
        article_id=article.id,
        slug=article.slug,
        admin_email=user.email,
        indexnow_url_count=len(url_list),
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
            raw_article_id=article.raw_article_id,
        )

    # Persist body scores so the admin list cards stay in sync with the
    # latest evaluator output. Only body scores feed the auto-flag — title
    # and excerpt are evaluated separately and don't drive ready_to_publish.
    # The text scored may be unsaved-in-editor; the score reflects the text
    # the editor JUST proofread, which is the intent ("ready for me to
    # publish this version"). If the editor discards the changes without
    # saving, the score on the card will be slightly ahead of the saved
    # body — acceptable, and self-correcting on the next proofread.
    persisted_to_card = False
    if payload.field == "body" and payload.lang in ("darija", "french"):
        threshold = settings.proofread_publish_ready_threshold
        naturalness_floor = settings.proofread_naturalness_floor
        if payload.lang == "darija":
            article.proofread_score_darija = result.score
        else:
            article.proofread_score_fr = result.score
        # Recompute readiness with the existing scores from the other
        # language (Darija required; FR optional). For the JUST-evaluated
        # language we have the naturalness sub-score in `result`; for the
        # other language we only have the headline score persisted in DB,
        # so the floor cannot be re-checked there — treated as "unknown,
        # not blocking" which matches the bulk-evaluate / pipeline rule.
        dr_score = article.proofread_score_darija
        fr_score = article.proofread_score_fr
        just_evaluated_nat = result.naturalness_score
        darija_passes = (
            dr_score is not None
            and dr_score >= threshold
            and (
                payload.lang != "darija"
                or just_evaluated_nat is None
                or just_evaluated_nat >= naturalness_floor
            )
        )
        fr_passes = fr_score is None or (
            fr_score >= threshold
            and (
                payload.lang != "french"
                or just_evaluated_nat is None
                or just_evaluated_nat >= naturalness_floor
            )
        )
        article.proofread_ready_to_publish = darija_passes and fr_passes
        article.proofread_at = datetime.now(UTC)
        article.updated_at = article.proofread_at
        await session.commit()
        await session.refresh(article)
        persisted_to_card = True

    logger.info(
        "admin.article.proofread",
        article_id=article_id,
        field=payload.field,
        lang=payload.lang,
        score=result.score,
        num_suggestions=len(result.suggestions),
        cached=result.cached,
        text_chars=len(payload.text),
        persisted_to_card=persisted_to_card,
        admin_email=user.email,
    )
    return result


@admin_router.post("/{article_id}/translate-to-fr", response_model=ArticleAdminDetail)
async def translate_article_to_french(
    article_id: int,
    session: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
) -> Article:
    """Auto-translate the article's Darija fields into French and persist them.

    Overwrites any existing French content — the admin UI is expected to ask
    the user before calling this when ``title_fr`` is non-empty.

    Backed by Claude Haiku 4.5 with a dedicated translator prompt; result is
    cached in Redis 30 days keyed by the Darija content hash so retries are
    free and deterministic.
    """
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise NotFoundError(
            f"Article {article_id} not found",
            details={"article_id": article_id},
        )

    settings = get_settings()
    async with _redis_for(settings) as redis_client:
        # Wrap so the manual "Re-translate" call lands in ai_logs too.
        provider = LoggingLLMProvider(ClaudeClient(settings.anthropic_api_key))
        translator = Translator(provider=provider, redis_client=redis_client)
        result = await translator.translate(
            title_darija=article.title_darija,
            excerpt_darija=article.excerpt_darija,
            content_darija=article.content_darija,
            meta_title=article.meta_title,
            meta_description=article.meta_description,
            raw_article_id=article.raw_article_id,
        )

    article.title_fr = result.title_fr or None
    article.excerpt_fr = result.excerpt_fr or None
    article.content_fr = result.content_fr or None
    article.meta_title_fr = result.meta_title_fr or None
    article.meta_description_fr = result.meta_description_fr or None
    article.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(article)

    logger.info(
        "admin.article.translated_to_fr",
        article_id=article.id,
        model=result.model,
        cached=result.cached,
        duration_ms=result.duration_ms,
        content_chars=len(result.content_fr),
        admin_email=user.email,
    )
    return article


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
