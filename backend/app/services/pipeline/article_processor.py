from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

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
from app.schemas.translate import TranslateToFrenchResult
from app.services.ai.ai_logging import LoggingLLMProvider, persist_ai_log
from app.services.ai.claude_client import ClaudeClient
from app.services.ai.localizer import LocalizedArticle, Localizer
from app.services.ai.quality_gate import QualityGate
from app.services.ai.translator import Translator
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
        translator: Translator | None = None,
    ) -> None:
        self._localizer = localizer
        self._quality_gate = quality_gate
        self._image_generator = image_generator
        self._translator = translator

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        redis: Redis,
        *,
        skip_image: bool = False,
        skip_translation: bool = False,
    ) -> ArticleProcessor:
        # The provider is wrapped so every Claude call lands in ai_logs.
        # Localizer + Translator share the same instance — costs roll up by
        # (provider, model) regardless of which service made the call.
        provider = LoggingLLMProvider(ClaudeClient(settings.anthropic_api_key))
        localizer = Localizer(
            provider=provider,
            redis_client=redis,
            prompt_version=settings.localizer_prompt_version,
        )
        image_generator = None if skip_image else _build_image_generator(settings)
        translator = None if skip_translation else Translator(provider=provider, redis_client=redis)
        return cls(
            localizer=localizer,
            quality_gate=QualityGate(),
            image_generator=image_generator,
            translator=translator,
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
                # Persist the failed image-gen attempt so cost dashboards see
                # the attempt even when no bytes came back.
                await persist_ai_log(
                    provider="replicate",
                    model=_image_provider_model(self._image_generator),
                    success=False,
                    cost_usd=Decimal("0"),
                    raw_article_id=raw_article_id,
                    error=str(exc),
                )
                await self._set_status(raw_article_id, STATUS_FAILED, reason=f"image: {exc}")
                return ProcessOutcome(
                    raw_article_id=raw_article_id,
                    status=STATUS_FAILED,
                    quality_passed=True,
                    failures=["image_failed"],
                    duration_ms=_elapsed_ms(t0),
                )
            # Success path — record the cost. ImageGenerator doesn't go through
            # the LLM provider abstraction, so we log here directly.
            await persist_ai_log(
                provider="replicate",
                model=_image_provider_model(self._image_generator),
                success=True,
                cost_usd=image_outcome.cost_usd,
                duration_ms=image_outcome.duration_ms,
                raw_article_id=raw_article_id,
            )

        # Auto-translate Darija → French. Fail-soft: a translation error
        # leaves the FR fields null but never blocks the draft (the admin can
        # click "Re-traduire en français" later to retry).
        translation: TranslateToFrenchResult | None = None
        if self._translator is not None:
            try:
                translation = await self._translator.translate(
                    title_darija=article.title_darija,
                    excerpt_darija=article.excerpt_darija,
                    content_darija=article.content_darija,
                    meta_title=article.meta_title,
                    meta_description=article.meta_description,
                    raw_article_id=raw_article_id,
                )
                log.info(
                    "article_processor.translated_to_fr",
                    raw_article_id=raw_article_id,
                    cached=translation.cached,
                    content_fr_chars=len(translation.content_fr),
                    duration_ms=translation.duration_ms,
                )
            except Exception as exc:
                # Don't block — keep the draft, the admin can re-translate.
                log.warning(
                    "article_processor.translation_failed_soft",
                    raw_article_id=raw_article_id,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                )

        article_id = await self._persist_draft(raw, article, image_outcome, translation)
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
        translation: TranslateToFrenchResult | None,
    ) -> int:
        """Upsert an Article row keyed by ``raw_article_id``, always unpublished."""
        assert raw.id is not None  # persisted row always has a PK
        # Pre-extract FR fields once so the insert/update branches stay symmetric.
        title_fr = translation.title_fr or None if translation else None
        excerpt_fr = translation.excerpt_fr or None if translation else None
        content_fr = translation.content_fr or None if translation else None
        meta_title_fr = translation.meta_title_fr or None if translation else None
        meta_description_fr = translation.meta_description_fr or None if translation else None

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
                    title_fr=title_fr,
                    excerpt_fr=excerpt_fr,
                    content_fr=content_fr,
                    meta_title_fr=meta_title_fr,
                    meta_description_fr=meta_description_fr,
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
                # Only overwrite FR fields when a fresh translation was produced —
                # don't clobber an existing FR draft when this run's translator
                # silently failed.
                if translation is not None:
                    existing.title_fr = title_fr
                    existing.excerpt_fr = excerpt_fr
                    existing.content_fr = content_fr
                    existing.meta_title_fr = meta_title_fr
                    existing.meta_description_fr = meta_description_fr
                existing.updated_at = datetime.now(UTC)
                row = existing
            await session.commit()
            await session.refresh(row)
            return int(row.id)  # type: ignore[arg-type]


def _image_provider_model(generator: ImageGenerator) -> str:
    """Best-effort extraction of the underlying image model name for ai_logs.

    ImageGenerator owns an ``ImageProvider`` whose concrete implementation
    (Replicate) carries a ``_model`` attribute. If the shape ever changes we
    fall back to a safe sentinel rather than crash the persist call.
    """
    provider = getattr(generator, "_provider", None)
    return getattr(provider, "_model", "unknown")


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
