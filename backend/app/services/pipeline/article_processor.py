from __future__ import annotations

import asyncio
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
from app.services.ai.french_localizer import FrenchLocalizer
from app.services.ai.localizer import LocalizedArticle, Localizer
from app.services.ai.proofreader import Proofreader
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


@dataclass
class ProofreadOutcome:
    """In-pipeline result of the auto-flag proofread step.

    Scores are ``None`` when the call fails or the language was not produced
    (e.g. translator skipped). ``ready_to_publish`` is the computed hint that
    surfaces as a green badge in the admin list — it never auto-publishes.
    """

    score_darija: int | None = None
    score_fr: int | None = None
    ready_to_publish: bool = False
    proofread_at: datetime | None = None


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
        french_localizer: FrenchLocalizer | None = None,
        translator: Translator | None = None,
        proofreader: Proofreader | None = None,
        proofread_publish_ready_threshold: int = 80,
        proofread_naturalness_floor: int = 75,
    ) -> None:
        self._localizer = localizer
        self._quality_gate = quality_gate
        self._image_generator = image_generator
        # `french_localizer` is the new direct EN→FR path. `translator` is the
        # legacy Darija→FR cascade kept around as a deprecated fallback for
        # back-compat (admin `Re-traduire en français` button still uses it).
        # Pipeline prefers `french_localizer` when both are set.
        self._french_localizer = french_localizer
        self._translator = translator
        self._proofreader = proofreader
        self._proofread_threshold = proofread_publish_ready_threshold
        self._proofread_naturalness_floor = proofread_naturalness_floor

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        redis: Redis,
        *,
        skip_image: bool = False,
        skip_translation: bool = False,
        skip_proofread: bool = False,
    ) -> ArticleProcessor:
        # Wrapped provider routes every Claude call through ai_logs. All three
        # AI services (Darija Localizer, FrenchLocalizer, Translator) share
        # the same instance so costs roll up by (provider, model) without
        # caring which service originated the call.
        provider = LoggingLLMProvider(ClaudeClient(settings.anthropic_api_key))
        localizer = Localizer(
            provider=provider,
            redis_client=redis,
            prompt_version=settings.localizer_prompt_version,
        )
        image_generator = None if skip_image else _build_image_generator(settings)
        # FR pipeline now defaults to direct EN→FR via FrenchLocalizer (PR
        # `feat/french-localizer-v1`). Translator is retained but no longer
        # wired into the pipeline — it remains reachable through the admin
        # endpoint until we confirm the new path is stable.
        french_localizer = (
            None if skip_translation else FrenchLocalizer(provider=provider, redis_client=redis)
        )
        # Proofreader uses OpenAI — only built when the key is set, otherwise
        # the auto-flag step is skipped silently and scores stay NULL.
        proofreader: Proofreader | None = None
        if not skip_proofread and settings.openai_api_key:
            proofreader = Proofreader(
                api_key=settings.openai_api_key,
                redis_client=redis,
                model=settings.proofreader_model,
            )
        return cls(
            localizer=localizer,
            quality_gate=QualityGate(),
            image_generator=image_generator,
            french_localizer=french_localizer,
            translator=None,  # legacy cascade no longer in the default pipeline
            proofreader=proofreader,
            proofread_publish_ready_threshold=settings.proofread_publish_ready_threshold,
            proofread_naturalness_floor=settings.proofread_naturalness_floor,
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
        raw_id = raw.id

        # Darija and French are now produced in parallel from the same EN
        # source. Darija is required (failure → article fails); French is
        # best-effort and absorbs its own errors so a French miss never
        # blocks publishing. Wall-clock for the two together is bounded by
        # the slower of the two calls (~5 s) instead of summed (~10 s).
        async def _safe_french() -> TranslateToFrenchResult | None:
            if self._french_localizer is None:
                return None
            try:
                return await self._french_localizer.localize(
                    title_en=raw.original_title,
                    content_en=raw.original_content,
                    source_name=source_name,
                    raw_article_id=raw_id,
                )
            except Exception as exc:
                log.warning(
                    "article_processor.french_localizer_failed_soft",
                    raw_article_id=raw_article_id,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                )
                return None

        try:
            article, french_translation = await asyncio.gather(
                self._localizer.localize(
                    title=raw.original_title,
                    content=raw.original_content,
                    source_name=source_name,
                    raw_article_id=raw.id,
                ),
                _safe_french(),
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

        # Pick up the French output produced in parallel above (or None if
        # FrenchLocalizer failed-soft / wasn't configured). When neither path
        # is configured AND a legacy Translator is still wired (e.g. older
        # test set-up), fall back to the cascade — kept here as a safety
        # net during the FrenchLocalizer observation window.
        translation: TranslateToFrenchResult | None = french_translation
        if translation is None and self._translator is not None:
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
                    "article_processor.translated_to_fr_cascade",
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
        elif translation is not None:
            log.info(
                "article_processor.localized_to_fr_direct",
                raw_article_id=raw_article_id,
                cached=translation.cached,
                content_fr_chars=len(translation.content_fr),
                duration_ms=translation.duration_ms,
            )

        # Auto-flag mode: run the AI Proofreader on the produced body in each
        # populated language. The result is a hint only — it never publishes
        # (CLAUDE.md §1). Fail-soft: scores stay NULL if anything goes wrong;
        # the admin's manual Re-évaluer button can be used to retry.
        proofread = await self._proofread_or_skip(
            raw_article_id=raw_article_id,
            content_darija=article.content_darija,
            content_fr=translation.content_fr if translation else None,
        )

        article_id = await self._persist_draft(raw, article, image_outcome, translation, proofread)
        await self._set_status(raw_article_id, STATUS_TRANSLATED)
        duration_ms = _elapsed_ms(t0)
        log.info(
            "article_processor.translated",
            raw_article_id=raw_article_id,
            article_id=article_id,
            word_count=article.word_count,
            proofread_score_darija=proofread.score_darija,
            proofread_score_fr=proofread.score_fr,
            proofread_ready_to_publish=proofread.ready_to_publish,
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

    async def _proofread_or_skip(
        self,
        *,
        raw_article_id: int,
        content_darija: str,
        content_fr: str | None,
    ) -> ProofreadOutcome:
        """Run the Proofreader on the body in each language; fail-soft.

        Returns a :class:`ProofreadOutcome` even when the Proofreader is
        disabled (no key, ``skip_proofread=True``) — in that case scores are
        ``None`` and ``ready_to_publish`` is ``False``. The pipeline persists
        the result either way so the admin sees a stable shape.
        """
        if self._proofreader is None:
            log.info(
                "article_processor.proofread_skipped",
                raw_article_id=raw_article_id,
                reason="proofreader_disabled",
            )
            return ProofreadOutcome()

        score_darija: int | None = None
        score_fr: int | None = None
        # Naturalness sub-score per language — needed for the v4 floor gate.
        # None means "we didn't get a sub-score back" (legacy cached entry,
        # parse failure) and the floor is treated as "not blocking" so we
        # don't reject articles for a missing measurement.
        nat_darija: int | None = None
        nat_fr: int | None = None

        try:
            result_darija = await self._proofreader.proofread(
                text=content_darija,
                lang="darija",
                field="body",
                raw_article_id=raw_article_id,
            )
            score_darija = result_darija.score
            nat_darija = result_darija.naturalness_score
        except Exception as exc:
            log.warning(
                "article_processor.proofread_darija_failed_soft",
                raw_article_id=raw_article_id,
                error=str(exc),
                error_type=exc.__class__.__name__,
            )

        if content_fr:
            try:
                result_fr = await self._proofreader.proofread(
                    text=content_fr,
                    lang="french",
                    field="body",
                    raw_article_id=raw_article_id,
                )
                score_fr = result_fr.score
                nat_fr = result_fr.naturalness_score
            except Exception as exc:
                log.warning(
                    "article_processor.proofread_fr_failed_soft",
                    raw_article_id=raw_article_id,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                )

        # Compute ready-to-publish: every populated language must clear BOTH
        # the headline threshold AND the naturalness floor. A missing
        # language (FR not produced) does not block. A missing naturalness
        # sub-score (legacy cached entry) does not block — only an explicit
        # naturalness below the floor blocks.
        threshold = self._proofread_threshold
        floor = self._proofread_naturalness_floor
        darija_passes = (
            score_darija is not None
            and score_darija >= threshold
            and (nat_darija is None or nat_darija >= floor)
        )
        fr_passes = score_fr is None or (
            score_fr >= threshold and (nat_fr is None or nat_fr >= floor)
        )
        ready = darija_passes and fr_passes

        # Only mark a proofread_at timestamp when SOMETHING was scored — a
        # double-failure run should not clobber prior scores in the upsert
        # branch of _persist_draft.
        any_score = score_darija is not None or score_fr is not None
        proofread_at = datetime.now(UTC) if any_score else None

        log.info(
            "article_processor.proofread_completed",
            raw_article_id=raw_article_id,
            score_darija=score_darija,
            score_fr=score_fr,
            naturalness_darija=nat_darija,
            naturalness_fr=nat_fr,
            threshold=threshold,
            naturalness_floor=floor,
            ready_to_publish=ready,
            persisted=any_score,
        )
        return ProofreadOutcome(
            score_darija=score_darija,
            score_fr=score_fr,
            ready_to_publish=ready,
            proofread_at=proofread_at,
        )

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
        proofread: ProofreadOutcome,
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
                    proofread_score_darija=proofread.score_darija,
                    proofread_score_fr=proofread.score_fr,
                    proofread_at=proofread.proofread_at,
                    proofread_ready_to_publish=proofread.ready_to_publish,
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
                # Same rule for proofread scores: only overwrite when this
                # run actually computed something. A failed proofread leaves
                # the existing scores untouched (the admin's prior manual
                # Re-évaluer may still be the source of truth).
                if proofread.proofread_at is not None:
                    existing.proofread_score_darija = proofread.score_darija
                    existing.proofread_score_fr = proofread.score_fr
                    existing.proofread_at = proofread.proofread_at
                    existing.proofread_ready_to_publish = proofread.ready_to_publish
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
