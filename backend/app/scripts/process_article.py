from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal, engine
from app.core.exceptions import AIQualityError
from app.core.logging import configure_logging, get_logger
from app.core.redis import get_redis_client
from app.models.article import Article
from app.models.raw_article import RawArticle
from app.models.source import Source
from app.services.ai.claude_client import ClaudeClient
from app.services.ai.critic_editor import CriticEditor, CriticEditorResult
from app.services.ai.cross_model_pipeline import CrossModelPipeline, CrossModelResult
from app.services.ai.llm_provider import LLMProvider, LLMResponse
from app.services.ai.localizer import LocalizedArticle, Localizer
from app.services.ai.openai_client import OpenAIClient
from app.services.ai.quality_gate import QualityCheckResult, QualityGate
from app.services.images.image_generator import ImageGenerationOutcome, ImageGenerator
from app.services.images.r2_storage import R2Storage
from app.services.images.replicate_client import ReplicateClient

DEFAULT_LOGS_DIR = Path("logs")
HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-4-6"
GPT_MINI = "gpt-4o-mini"
MODES = ("haiku-only", "sonnet-only", "two-pass", "cross-model", "openai-only")


class CostTrackingProvider:
    """LLMProvider wrapper that accumulates cost across calls."""

    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self.total_cost: Decimal = Decimal("0")

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def default_model(self) -> str:
        return self._inner.default_model

    async def complete(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        metadata: dict[str, str] | None = None,
    ) -> LLMResponse:
        response = await self._inner.complete(
            system=system,
            user=user,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            metadata=metadata,
        )
        self.total_cost += response.cost_usd
        return response


def _format_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def _write_markdown(
    *,
    output_path: Path,
    mode: str,
    article_id: int,
    writer_model: str,
    critic_model: str | None,
    total_cost_usd: Decimal,
    total_duration_ms: int,
    quality: QualityCheckResult,
    article: LocalizedArticle,
    corrections: list[str] | None,
    corrections_count: int | str,
    raw_title: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    front = (
        f"---\n"
        f"mode: {mode}\n"
        f"article_id: {article_id}\n"
        f"writer_model: {writer_model}\n"
        f"critic_model: {critic_model or 'n/a'}\n"
        f"total_cost_usd: {total_cost_usd}\n"
        f"total_duration_ms: {total_duration_ms}\n"
        f"quality_gate: {'passed' if quality.passed else 'failed'}\n"
        f"quality_failures: {_format_list(quality.failures)}\n"
        f"quality_warnings: {_format_list(quality.warnings)}\n"
        f"word_count: {article.word_count}\n"
        f"corrections_count: {corrections_count}\n"
        f"original_title: {json.dumps(raw_title, ensure_ascii=False)}\n"
        f"slug: {article.slug}\n"
        f"---\n\n"
    )
    body = f"# {article.title_darija}\n\n*{article.excerpt_darija}*\n\n{article.content_darija}\n"
    suffix = ""
    if corrections is not None:
        bullets = "\n".join(f"- {c}" for c in corrections) or "- (none reported)"
        suffix = f"\n---\n\n## Corrections made (two-pass only)\n{bullets}\n"

    output_path.write_text(front + body + suffix, encoding="utf-8")


def _print_run_report(
    *,
    mode: str,
    article_id: int,
    writer_model: str,
    critic_model: str | None,
    article: LocalizedArticle,
    quality: QualityCheckResult,
    total_cost_usd: Decimal,
    total_duration_ms: int,
    corrections_count: int | str,
    output_path: Path,
    image_outcome: ImageGenerationOutcome | None = None,
    persisted_article_id: int | None = None,
) -> None:
    bar = "=" * 78
    print(bar)
    print(f"MODE: {mode}  | article #{article_id}")
    print(bar)
    print(f"writer_model:       {writer_model}")
    print(f"critic_model:       {critic_model or 'n/a'}")
    if image_outcome is not None:
        combined_cost = total_cost_usd + image_outcome.cost_usd
        print(f"localizer_cost:     ${total_cost_usd}")
        print(f"image_cost:         ${image_outcome.cost_usd}")
        print(f"total_cost_usd:     ${combined_cost}")
    else:
        print(f"total_cost_usd:     ${total_cost_usd}")
    print(f"total_duration_ms:  {total_duration_ms} ms")
    print(f"word_count:         {article.word_count}")
    print(f"corrections_count:  {corrections_count}")
    print(f"quality_gate:       {'passed' if quality.passed else 'FAILED'}")
    print(f"quality_failures:   {quality.failures or 'none'}")
    print(f"quality_warnings:   {quality.warnings or 'none'}")
    if image_outcome is not None:
        print(f"image_url:          {image_outcome.public_url}")
        print(f"image_dimensions:   {image_outcome.width}x{image_outcome.height}")
        print(f"image_duration_ms:  {image_outcome.duration_ms} ms")
    if persisted_article_id is not None:
        print(f"db_article_id:      {persisted_article_id}  (is_published=False)")
    print(f"output:             {output_path.resolve()}")
    print(bar)


async def _load_article(article_id: int) -> tuple[RawArticle, str]:
    async with AsyncSessionLocal() as session:
        raw = await session.scalar(select(RawArticle).where(RawArticle.id == article_id))
        if raw is None:
            raise SystemExit(f"raw_article id={article_id} not found")
        source_name = "unknown"
        if raw.source_id:
            src = await session.scalar(select(Source).where(Source.id == raw.source_id))
            if src:
                source_name = src.name
    return raw, source_name


async def main(article_id: int, mode: str, output: Path, skip_image: bool = False) -> int:
    configure_logging()
    log = get_logger("scripts.process_article")
    settings = get_settings()

    if mode not in MODES:
        print(f"unknown mode {mode!r}; expected one of {MODES}", file=sys.stderr)
        return 2

    raw, source_name = await _load_article(article_id)

    redis = get_redis_client()
    try:
        if mode == "cross-model":
            return await _run_cross_model(
                raw=raw,
                source_name=source_name,
                output=output,
                redis=redis,
                settings=settings,
                log=log,
            )
        if mode == "openai-only":
            return await _run_openai_only(
                raw=raw,
                source_name=source_name,
                output=output,
                redis=redis,
                settings=settings,
                log=log,
            )

        if mode == "haiku-only":
            writer_model, critic_model = HAIKU, None
        elif mode == "sonnet-only":
            writer_model, critic_model = SONNET, None
        else:
            writer_model, critic_model = HAIKU, SONNET

        base_provider = ClaudeClient(settings.anthropic_api_key)
        provider = CostTrackingProvider(base_provider)
        localizer = Localizer(provider=provider, redis_client=redis, model=writer_model)
        quality_gate = QualityGate()

        t0 = time.perf_counter()
        try:
            draft = await localizer.localize(
                title=raw.original_title,
                content=raw.original_content,
                source_name=source_name,
                raw_article_id=raw.id,
            )
        except AIQualityError as exc:
            log.error(
                "process_article.localizer_failed",
                article_id=article_id,
                details=exc.details,
            )
            print(f"Localizer failed: {exc.message}", file=sys.stderr)
            return 1

        critic_result: CriticEditorResult | None = None
        final_article = draft
        corrections_field: int | str = "n/a"
        corrections_list: list[str] | None = None

        if mode == "two-pass":
            critic = CriticEditor(provider=provider, model=critic_model)
            try:
                critic_result = await critic.review(
                    draft=draft,
                    original_source=raw.original_content,
                )
            except AIQualityError as exc:
                log.error(
                    "process_article.critic_failed",
                    article_id=article_id,
                    details=exc.details,
                )
                print(f"Critic failed: {exc.message}", file=sys.stderr)
                return 1
            final_article = critic_result.corrected_article
            corrections_field = critic_result.corrections_count
            corrections_list = critic_result.corrections_made

        total_duration_ms = int((time.perf_counter() - t0) * 1000)
        total_cost_usd = provider.total_cost

        quality = quality_gate.check(final_article)

        _write_markdown(
            output_path=output,
            mode=mode,
            article_id=article_id,
            writer_model=writer_model,
            critic_model=critic_model,
            total_cost_usd=total_cost_usd,
            total_duration_ms=total_duration_ms,
            quality=quality,
            article=final_article,
            corrections=corrections_list,
            corrections_count=corrections_field,
            raw_title=raw.original_title,
        )

        # Image generation + DB persistence: production-shape modes only.
        image_outcome: ImageGenerationOutcome | None = None
        persisted_id: int | None = None
        is_production_mode = mode in ("haiku-only", "sonnet-only", "two-pass")
        if is_production_mode and quality.passed:
            if not skip_image:
                try:
                    image_outcome = await _generate_image(
                        prompt=final_article.image_prompt,
                        slug=final_article.slug,
                        settings=settings,
                    )
                except Exception as exc:
                    log.error(
                        "process_article.image_failed",
                        article_id=article_id,
                        error=str(exc),
                        error_type=exc.__class__.__name__,
                    )
                    print(f"Image generation failed: {exc}", file=sys.stderr)
                    return 1
            persisted_id = await _persist_article(
                raw=raw,
                final_article=final_article,
                image_outcome=image_outcome,
            )

        _print_run_report(
            mode=mode,
            article_id=article_id,
            writer_model=writer_model,
            critic_model=critic_model,
            article=final_article,
            quality=quality,
            total_cost_usd=total_cost_usd,
            total_duration_ms=total_duration_ms,
            corrections_count=corrections_field,
            output_path=output,
            image_outcome=image_outcome,
            persisted_article_id=persisted_id,
        )

        return 0 if quality.passed else 1
    finally:
        await redis.aclose()
        await engine.dispose()


async def _generate_image(
    *,
    prompt: str,
    slug: str,
    settings,  # type: ignore[no-untyped-def]
) -> ImageGenerationOutcome:
    """Build provider/storage from settings and generate+upload one image."""
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
    return await generator.generate_and_upload(prompt=prompt, article_slug=slug)


async def _persist_article(
    *,
    raw: RawArticle,
    final_article: LocalizedArticle,
    image_outcome: ImageGenerationOutcome | None,
) -> int:
    """Upsert an Article row keyed by raw_article_id. Returns the article id.

    Always saves with ``is_published=False`` — publication is a manual step in
    the admin panel (ADR-002).
    """
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(Article).where(Article.raw_article_id == raw.id))
        if existing is None:
            article = Article(
                raw_article_id=raw.id,
                slug=final_article.slug,
                title_darija=final_article.title_darija,
                excerpt_darija=final_article.excerpt_darija,
                content_darija=final_article.content_darija,
                meta_title=final_article.meta_title,
                meta_description=final_article.meta_description,
                hero_image_url=image_outcome.public_url if image_outcome else None,
                hero_image_alt=final_article.title_darija if image_outcome else None,
                categories=final_article.categories,
                tags=final_article.tags,
                reading_time_minutes=final_article.reading_time_minutes,
                word_count=final_article.word_count,
                is_published=False,
            )
            session.add(article)
        else:
            existing.slug = final_article.slug
            existing.title_darija = final_article.title_darija
            existing.excerpt_darija = final_article.excerpt_darija
            existing.content_darija = final_article.content_darija
            existing.meta_title = final_article.meta_title
            existing.meta_description = final_article.meta_description
            if image_outcome:
                existing.hero_image_url = image_outcome.public_url
                existing.hero_image_alt = final_article.title_darija
            existing.categories = final_article.categories
            existing.tags = final_article.tags
            existing.reading_time_minutes = final_article.reading_time_minutes
            existing.word_count = final_article.word_count
            existing.updated_at = datetime.now(UTC)
            article = existing
        await session.commit()
        await session.refresh(article)
        return int(article.id)  # type: ignore[arg-type]


async def _run_cross_model(
    *,
    raw: RawArticle,
    source_name: str,
    output: Path,
    redis,  # type: ignore[no-untyped-def]
    settings,  # type: ignore[no-untyped-def]
    log,  # type: ignore[no-untyped-def]
) -> int:
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is required for cross-model mode", file=sys.stderr)
        return 2

    writer_provider = ClaudeClient(settings.anthropic_api_key, default_model=HAIKU)
    rewriter_provider = ClaudeClient(settings.anthropic_api_key, default_model=HAIKU)
    critic_provider = OpenAIClient(settings.openai_api_key, default_model=GPT_MINI)

    pipeline = CrossModelPipeline(
        writer_provider=writer_provider,
        critic_provider=critic_provider,
        rewriter_provider=rewriter_provider,
        writer_model=HAIKU,
        critic_model=GPT_MINI,
        rewriter_model=HAIKU,
        writer_redis=redis,
    )
    quality_gate = QualityGate()

    try:
        result = await pipeline.process(
            title=raw.original_title,
            content=raw.original_content,
            source_name=source_name,
            raw_article_id=raw.id,
        )
    except AIQualityError as exc:
        log.error(
            "process_article.cross_model_failed",
            article_id=raw.id,
            details=exc.details,
        )
        print(f"Cross-model pipeline failed: {exc.message}", file=sys.stderr)
        return 1

    quality = quality_gate.check(result.final_article)
    _write_cross_model_markdown(
        output_path=output,
        mode="cross-model",
        article_id=raw.id,
        result=result,
        quality=quality,
        raw_title=raw.original_title,
    )
    _print_cross_model_report(
        mode="cross-model",
        article_id=raw.id,
        result=result,
        quality=quality,
        output_path=output,
    )
    return 0 if quality.passed else 1


async def _run_openai_only(
    *,
    raw: RawArticle,
    source_name: str,
    output: Path,
    redis,  # type: ignore[no-untyped-def]
    settings,  # type: ignore[no-untyped-def]
    log,  # type: ignore[no-untyped-def]
) -> int:
    """Sanity-check mode: GPT-4o-mini for writer, critic, and rewriter.
    Validates the 3-pass pipeline mechanics. Darija quality is expected to be poor."""
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is required for openai-only mode", file=sys.stderr)
        return 2

    writer_provider = OpenAIClient(settings.openai_api_key, default_model=GPT_MINI)
    critic_provider = OpenAIClient(settings.openai_api_key, default_model=GPT_MINI)
    rewriter_provider = OpenAIClient(settings.openai_api_key, default_model=GPT_MINI)

    pipeline = CrossModelPipeline(
        writer_provider=writer_provider,
        critic_provider=critic_provider,
        rewriter_provider=rewriter_provider,
        writer_model=GPT_MINI,
        critic_model=GPT_MINI,
        rewriter_model=GPT_MINI,
        writer_redis=redis,
    )
    quality_gate = QualityGate()

    try:
        result = await pipeline.process(
            title=raw.original_title,
            content=raw.original_content,
            source_name=source_name,
            raw_article_id=raw.id,
        )
    except AIQualityError as exc:
        log.error(
            "process_article.openai_only_failed",
            article_id=raw.id,
            details=exc.details,
        )
        print(f"Pipeline failed: {exc.message}", file=sys.stderr)
        return 1

    quality = quality_gate.check(result.final_article)
    _write_cross_model_markdown(
        output_path=output,
        mode="openai-only",
        article_id=raw.id,
        result=result,
        quality=quality,
        raw_title=raw.original_title,
    )
    _print_cross_model_report(
        mode="openai-only",
        article_id=raw.id,
        result=result,
        quality=quality,
        output_path=output,
    )
    return 0 if quality.passed else 1


def _write_cross_model_markdown(
    *,
    output_path: Path,
    mode: str,
    article_id: int,
    result: CrossModelResult,
    quality: QualityCheckResult,
    raw_title: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    article = result.final_article
    front = (
        f"---\n"
        f"mode: {mode}\n"
        f"article_id: {article_id}\n"
        f"writer_model: {result.writer_model}\n"
        f"critic_model: {result.critic_model}\n"
        f"rewriter_model: {result.rewriter_model}\n"
        f"writer_cost_usd: {result.writer_cost}\n"
        f"critic_cost_usd: {result.critic_cost}\n"
        f"rewriter_cost_usd: {result.rewriter_cost}\n"
        f"total_cost_usd: {result.total_cost}\n"
        f"total_duration_ms: {result.total_duration_ms}\n"
        f"overall_quality_score: {result.overall_quality_score}\n"
        f"defects_count: {len(result.defects_found)}\n"
        f"defects_count_by_category: {json.dumps(result.defects_count_by_category, ensure_ascii=False)}\n"  # noqa: E501
        f"corrections_count: {len(result.corrections_applied)}\n"
        f"rewriter_skipped: {result.rewriter_skipped}\n"
        f"quality_gate: {'passed' if quality.passed else 'failed'}\n"
        f"quality_failures: {_format_list(quality.failures)}\n"
        f"quality_warnings: {_format_list(quality.warnings)}\n"
        f"word_count: {article.word_count}\n"
        f"original_title: {json.dumps(raw_title, ensure_ascii=False)}\n"
        f"slug: {article.slug}\n"
        f"---\n\n"
    )
    body = f"# {article.title_darija}\n\n*{article.excerpt_darija}*\n\n{article.content_darija}\n"
    defects_section = ""
    if result.defects_found:
        defects_section = "\n---\n\n## Defects flagged by GPT critic\n"
        for d in result.defects_found:
            defects_section += (
                f"\n- **[{d.get('category', '?')}/{d.get('severity', '?')}]** "
                f"({d.get('location', '?')}): {d.get('issue', '')}\n"
                f"  - suggested_fix: {d.get('suggested_fix', '')}\n"
            )
    corrections_section = ""
    if result.corrections_applied:
        corrections_section = "\n---\n\n## Corrections applied by Haiku rewriter\n"
        for c in result.corrections_applied:
            corrections_section += f"- {c}\n"

    output_path.write_text(front + body + defects_section + corrections_section, encoding="utf-8")


def _print_cross_model_report(
    *,
    mode: str,
    article_id: int,
    result: CrossModelResult,
    quality: QualityCheckResult,
    output_path: Path,
) -> None:
    bar = "=" * 78
    print(bar)
    print(f"MODE: {mode}  | article #{article_id}")
    print(bar)
    print(f"writer_model:        {result.writer_model}")
    print(f"critic_model:        {result.critic_model}")
    print(f"rewriter_model:      {result.rewriter_model}")
    print(f"writer_cost_usd:     ${result.writer_cost}")
    print(f"critic_cost_usd:     ${result.critic_cost}")
    print(f"rewriter_cost_usd:   ${result.rewriter_cost}")
    print(f"total_cost_usd:      ${result.total_cost}")
    print(f"total_duration_ms:   {result.total_duration_ms} ms")
    print(f"word_count:          {result.final_article.word_count}")
    print(f"quality_score:       {result.overall_quality_score}")
    print(f"defects_found:       {len(result.defects_found)}")
    print(f"defects_by_cat:      {result.defects_count_by_category}")
    print(f"corrections_applied: {len(result.corrections_applied)}")
    print(f"rewriter_skipped:    {result.rewriter_skipped}")
    print(f"quality_gate:        {'passed' if quality.passed else 'FAILED'}")
    print(f"quality_failures:    {quality.failures or 'none'}")
    print(f"quality_warnings:    {quality.warnings or 'none'}")
    print(f"output:              {output_path.resolve()}")
    print(bar)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Localize one raw_article in a chosen mode.")
    parser.add_argument("--article-id", type=int, required=True)
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="haiku-only",
        help="Pipeline mode (default: haiku-only, the production config per ADR-002).",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--skip-image",
        action="store_true",
        help="Skip Replicate image generation and R2 upload (production modes only).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    output_path = args.output or DEFAULT_LOGS_DIR / f"localized_{args.article_id}_{args.mode}.md"
    sys.exit(asyncio.run(main(args.article_id, args.mode, output_path, args.skip_image)))
