from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlmodel import col

from app.core.config import Settings
from app.core.db import AsyncSessionLocal
from app.core.exceptions import AIQualityError
from app.core.logging import get_logger
from app.models.article import Article
from app.models.raw_article import RawArticle
from app.models.source import Source
from app.services.ai.claude_client import ClaudeClient
from app.services.ai.localizer import LocalizedArticle, Localizer
from app.services.ai.quality_gate import QualityGate
from app.services.images.image_generator import ImageGenerationOutcome, ImageGenerator
from app.services.images.r2_storage import R2Storage
from app.services.images.replicate_client import ReplicateClient

log = get_logger("services.pipeline.article_processor")

# raw_article.processing_status values reached by this service.
STATUS_PROCESSING = "processing"
STATUS_TRANSLATED = "translated"
STATUS_REJECTED = "rejected"
STATUS_FAILED = "failed"


@dataclass
class ProcessOutcome:
    """Result of running the per-article pipeline once.

    ``status`` mirrors the value written to ``raw_article.processing_status``.
    Pipeline errors are recorded (status ``failed``) rather than raised, so the
    caller can decide whether to re-enqueue via the ``retry_failed`` job.
    """

    raw_article_id: int
    status: str
    quality_passed: bool
    article_id: int | None = None
    failures: list[str] = field(default_factory=list)
    duration_ms: int = 0


class ArticleProcessor:
    """Localize one raw article into a Darija draft (``is_published=False``).

    Steps: localize (Haiku) → quality gate → image (Flux/R2) → persist draft.
    Owns its DB sessions and manages ``raw_article.processing_status``
    transitions. Collaborators are injected for testability; use
    :meth:`from_settings` for the production wiring.

    All drafts are saved unpublished — publication is a manual admin step
    (ADR-002, human-review-mandatory).
    """

    def __init__(
        self,
        *,
        localizer: Localizer,
        quality_gate: QualityGate,
        image_generator: ImageGenerator | None,
    ) -> None:
        self._localizer = localizer
        self._quality_gate = quality_gate
        self._image_generator = image_generator

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        redis: Redis,
        *,
        skip_image: bool = False,
    ) -> ArticleProcessor:
        provider = ClaudeClient(settings.anthropic_api_key)
        localizer = Localizer(
            provider=provider,
            redis_client=redis,
            prompt_version=settings.localizer_prompt_version,
        )
        image_generator = None if skip_image else _build_image_generator(settings)
        return cls(
            localizer=localizer,
            quality_gate=QualityGate(),
            image_generator=image_generator,
        )

    async def process(self, raw_article_id: int) -> ProcessOutcome:
        t0 = time.perf_counter()
        raw, source_name = await self._load_and_mark_processing(raw_article_id)
        if raw is None:
            log.warning("article_processor.raw_not_found", raw_article_id=raw_article_id)
            return ProcessOutcome(
                raw_article_id=raw_article_id,
                status=STATUS_FAILED,
                quality_passed=False,
                failures=["raw_article_not_found"],
                duration_ms=_elapsed_ms(t0),
            )
        assert raw.id is not None  # loaded row always has a PK

        try:
            article = await self._localizer.localize(
                title=raw.original_title,
                content=raw.original_content,
                source_name=source_name,
                raw_article_id=raw.id,
            )
        except AIQualityError as exc:
            log.error(
                "article_processor.localizer_failed",
                raw_article_id=raw_article_id,
                details=exc.details,
            )
            await self._set_status(raw_article_id, STATUS_FAILED, reason=exc.message)
            return ProcessOutcome(
                raw_article_id=raw_article_id,
                status=STATUS_FAILED,
                quality_passed=False,
                failures=["localizer_failed"],
                duration_ms=_elapsed_ms(t0),
            )

        quality = self._quality_gate.check(article)
        if not quality.passed:
            log.info(
                "article_processor.quality_rejected",
                raw_article_id=raw_article_id,
                failures=quality.failures,
            )
            await self._set_status(
                raw_article_id,
                STATUS_REJECTED,
                reason="; ".join(quality.failures),
            )
            return ProcessOutcome(
                raw_article_id=raw_article_id,
                status=STATUS_REJECTED,
                quality_passed=False,
                failures=quality.failures,
                duration_ms=_elapsed_ms(t0),
            )

        image_outcome: ImageGenerationOutcome | None = None
        if self._image_generator is not None:
            try:
                image_outcome = await self._image_generator.generate_and_upload(
                    prompt=article.image_prompt,
                    article_slug=article.slug,
                )
            except Exception as exc:
                log.error(
                    "article_processor.image_failed",
                    raw_article_id=raw_article_id,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                )
                await self._set_status(raw_article_id, STATUS_FAILED, reason=f"image: {exc}")
                return ProcessOutcome(
                    raw_article_id=raw_article_id,
                    status=STATUS_FAILED,
                    quality_passed=True,
                    failures=["image_failed"],
                    duration_ms=_elapsed_ms(t0),
                )

        article_id = await self._persist_draft(raw, article, image_outcome)
        await self._set_status(raw_article_id, STATUS_TRANSLATED)
        duration_ms = _elapsed_ms(t0)
        log.info(
            "article_processor.translated",
            raw_article_id=raw_article_id,
            article_id=article_id,
            word_count=article.word_count,
            duration_ms=duration_ms,
        )
        return ProcessOutcome(
            raw_article_id=raw_article_id,
            status=STATUS_TRANSLATED,
            quality_passed=True,
            article_id=article_id,
            duration_ms=duration_ms,
        )

    async def _load_and_mark_processing(self, raw_article_id: int) -> tuple[RawArticle | None, str]:
        async with AsyncSessionLocal() as session:
            raw = await session.get(RawArticle, raw_article_id)
            if raw is None:
                return None, "unknown"
            source_name = "unknown"
            if raw.source_id:
                src = await session.scalar(select(Source).where(col(Source.id) == raw.source_id))
                if src:
                    source_name = src.name
            raw.processing_status = STATUS_PROCESSING
            await session.commit()
            await session.refresh(raw)
            return raw, source_name

    async def _set_status(
        self, raw_article_id: int, status: str, *, reason: str | None = None
    ) -> None:
        async with AsyncSessionLocal() as session:
            raw = await session.get(RawArticle, raw_article_id)
            if raw is None:
                return
            raw.processing_status = status
            if reason is not None:
                raw.rejection_reason = reason
            await session.commit()

    async def _persist_draft(
        self,
        raw: RawArticle,
        article: LocalizedArticle,
        image_outcome: ImageGenerationOutcome | None,
    ) -> int:
        """Upsert an Article row keyed by ``raw_article_id``, always unpublished."""
        assert raw.id is not None  # persisted row always has a PK
        async with AsyncSessionLocal() as session:
            existing = await session.scalar(
                select(Article).where(col(Article.raw_article_id) == raw.id)
            )
            if existing is None:
                row = Article(
                    raw_article_id=raw.id,
                    slug=article.slug,
                    title_darija=article.title_darija,
                    excerpt_darija=article.excerpt_darija,
                    content_darija=article.content_darija,
                    meta_title=article.meta_title,
                    meta_description=article.meta_description,
                    hero_image_url=image_outcome.public_url if image_outcome else None,
                    hero_image_alt=article.title_darija if image_outcome else None,
                    categories=article.categories,
                    tags=article.tags,
                    reading_time_minutes=article.reading_time_minutes,
                    word_count=article.word_count,
                    is_published=False,
                )
                session.add(row)
            else:
                existing.slug = article.slug
                existing.title_darija = article.title_darija
                existing.excerpt_darija = article.excerpt_darija
                existing.content_darija = article.content_darija
                existing.meta_title = article.meta_title
                existing.meta_description = article.meta_description
                if image_outcome:
                    existing.hero_image_url = image_outcome.public_url
                    existing.hero_image_alt = article.title_darija
                existing.categories = article.categories
                existing.tags = article.tags
                existing.reading_time_minutes = article.reading_time_minutes
                existing.word_count = article.word_count
                existing.updated_at = datetime.now(UTC)
                row = existing
            await session.commit()
            await session.refresh(row)
            return int(row.id)  # type: ignore[arg-type]


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


def _elapsed_ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)
