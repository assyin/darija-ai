from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis

from app.core.exceptions import AIQualityError
from app.core.logging import get_logger
from app.services.ai.bidi import (
    count_wrapped_terms,
    strip_bdi_tags,
    wrap_latin_with_bdi,
)
from app.services.ai.llm_provider import LLMProvider, LLMResponse
from app.services.ai.localizer import REQUIRED_FIELDS, LocalizedArticle, Localizer
from app.services.ai.prompt_loader import PromptLoader

logger = get_logger("services.ai.cross_model_pipeline")

_BIDI_FIELDS: tuple[str, ...] = (
    "title_darija",
    "excerpt_darija",
    "content_darija",
    "meta_title",
    "meta_description",
)


@dataclass(frozen=True)
class CrossModelResult:
    final_article: LocalizedArticle
    writer_cost: Decimal
    critic_cost: Decimal
    rewriter_cost: Decimal
    total_cost: Decimal
    total_duration_ms: int
    defects_found: list[dict[str, Any]] = field(default_factory=list)
    defects_count_by_category: dict[str, int] = field(default_factory=dict)
    corrections_applied: list[str] = field(default_factory=list)
    overall_quality_score: str = "unknown"
    rewriter_skipped: bool = False
    writer_model: str = ""
    critic_model: str = ""
    rewriter_model: str = ""


class _CostTracker:
    """Wraps an LLMProvider, accumulating cost across calls."""

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


def _strip_json_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1 :]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def _draft_to_clean_dict(draft: LocalizedArticle) -> dict[str, Any]:
    return {
        "title_darija": strip_bdi_tags(draft.title_darija),
        "slug": draft.slug,
        "excerpt_darija": strip_bdi_tags(draft.excerpt_darija),
        "content_darija": strip_bdi_tags(draft.content_darija),
        "meta_title": strip_bdi_tags(draft.meta_title),
        "meta_description": strip_bdi_tags(draft.meta_description),
        "categories": draft.categories,
        "tags": draft.tags,
        "image_prompt": draft.image_prompt,
    }


class CrossModelPipeline:
    """Three-pass cross-model pipeline: writer (Claude) → critic (GPT) → rewriter (Claude)."""

    def __init__(
        self,
        writer_provider: LLMProvider,
        critic_provider: LLMProvider,
        rewriter_provider: LLMProvider,
        writer_model: str = "claude-haiku-4-5",
        critic_model: str | None = None,
        rewriter_model: str = "claude-haiku-4-5",
        writer_redis: Redis | None = None,
        localizer_prompt_version: str = "v1",
        critic_prompt_version: str = "v1",
        rewriter_prompt_version: str = "v1",
    ):
        self._writer_tracker = _CostTracker(writer_provider)
        self._critic_tracker = _CostTracker(critic_provider)
        self._rewriter_tracker = _CostTracker(rewriter_provider)

        self._writer_model = writer_model
        self._critic_model = critic_model or critic_provider.default_model
        self._rewriter_model = rewriter_model

        self._localizer = Localizer(
            provider=self._writer_tracker,
            redis_client=writer_redis,
            model=writer_model,
            prompt_version=localizer_prompt_version,
        )
        self._critic_prompt_version = critic_prompt_version
        self._rewriter_prompt_version = rewriter_prompt_version

    async def process(
        self,
        *,
        title: str,
        content: str,
        source_name: str,
        raw_article_id: int,
    ) -> CrossModelResult:
        run_start = time.perf_counter()

        # ------- Pass 1: writer -------
        logger.info(
            "cross_model.writer.started",
            raw_article_id=raw_article_id,
            model=self._writer_model,
        )
        draft = await self._localizer.localize(
            title=title,
            content=content,
            source_name=source_name,
            raw_article_id=raw_article_id,
        )
        writer_cost = self._writer_tracker.total_cost

        # ------- Pass 2: critic (cross-family) -------
        critic_payload = await self._run_critic(
            draft=draft,
            original_source=content,
            raw_article_id=raw_article_id,
        )
        critic_cost = self._critic_tracker.total_cost
        defects = list(critic_payload.get("defects_found") or [])
        defects_count_by_category = dict(
            critic_payload.get("defects_count_by_category") or {}
        )
        quality_score = str(critic_payload.get("overall_quality_score") or "unknown")

        # ------- Pass 3: rewriter (skip if clean) -------
        rewriter_skipped = False
        corrections_applied: list[str] = []
        final_article = draft

        if not defects and quality_score == "good":
            logger.info(
                "cross_model.rewriter.skipped",
                raw_article_id=raw_article_id,
                reason="critic_found_no_defects",
            )
            rewriter_skipped = True
        else:
            final_article, corrections_applied = await self._run_rewriter(
                draft=draft,
                defects=defects,
                raw_article_id=raw_article_id,
            )

        rewriter_cost = self._rewriter_tracker.total_cost
        total_duration_ms = int((time.perf_counter() - run_start) * 1000)
        total_cost = writer_cost + critic_cost + rewriter_cost

        logger.info(
            "cross_model.completed",
            raw_article_id=raw_article_id,
            writer_cost=str(writer_cost),
            critic_cost=str(critic_cost),
            rewriter_cost=str(rewriter_cost),
            total_cost=str(total_cost),
            total_duration_ms=total_duration_ms,
            defects_count=len(defects),
            corrections_count=len(corrections_applied),
            rewriter_skipped=rewriter_skipped,
            quality_score=quality_score,
        )

        return CrossModelResult(
            final_article=final_article,
            writer_cost=writer_cost,
            critic_cost=critic_cost,
            rewriter_cost=rewriter_cost,
            total_cost=total_cost,
            total_duration_ms=total_duration_ms,
            defects_found=defects,
            defects_count_by_category=defects_count_by_category,
            corrections_applied=corrections_applied,
            overall_quality_score=quality_score,
            rewriter_skipped=rewriter_skipped,
            writer_model=self._writer_model,
            critic_model=self._critic_model,
            rewriter_model=self._rewriter_model,
        )

    # ------------------------------------------------------------------
    # Pass 2 — critic
    # ------------------------------------------------------------------

    async def _run_critic(
        self,
        *,
        draft: LocalizedArticle,
        original_source: str,
        raw_article_id: int,
    ) -> dict[str, Any]:
        system = PromptLoader.load("critic", self._critic_prompt_version)
        clean = _draft_to_clean_dict(draft)
        user = (
            "ORIGINAL ARTICLE:\n"
            f"{original_source[:5000]}\n\n"
            "DRAFT DARIJA (JSON):\n"
            f"{json.dumps(clean, ensure_ascii=False, indent=2)}"
        )

        logger.info(
            "cross_model.critic.started",
            raw_article_id=raw_article_id,
            model=self._critic_model,
        )

        response = await self._critic_tracker.complete(
            system=system,
            user=user,
            model=self._critic_model,
            max_tokens=4096,
            temperature=0.0,
            metadata={"user_id": "critic"},
        )

        # Parse with one tolerant retry: ask for stricter JSON-only.
        try:
            parsed = self._parse_critic_json(response.text)
        except AIQualityError:
            logger.warning(
                "cross_model.critic.parse_retry",
                raw_article_id=raw_article_id,
            )
            stricter_user = (
                user
                + "\n\nIMPORTANT: Return ONLY a JSON object. No prose, no markdown fences, no comments."
            )
            response2 = await self._critic_tracker.complete(
                system=system,
                user=stricter_user,
                model=self._critic_model,
                max_tokens=4096,
                temperature=0.0,
                metadata={"user_id": "critic-retry"},
            )
            parsed = self._parse_critic_json(response2.text)

        logger.info(
            "cross_model.critic.completed",
            raw_article_id=raw_article_id,
            duration_ms=response.duration_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=str(response.cost_usd),
            defects=len(parsed.get("defects_found") or []),
            quality=parsed.get("overall_quality_score"),
        )
        return parsed

    @staticmethod
    def _parse_critic_json(raw_text: str) -> dict[str, Any]:
        cleaned = _strip_json_fence(raw_text)
        try:
            parsed: Any = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIQualityError(
                "Critic returned invalid JSON",
                details={"reason": "invalid_json", "error": str(exc)},
            ) from exc
        if not isinstance(parsed, dict):
            raise AIQualityError(
                "Critic JSON must be an object",
                details={"reason": "not_an_object"},
            )
        return parsed

    # ------------------------------------------------------------------
    # Pass 3 — rewriter
    # ------------------------------------------------------------------

    async def _run_rewriter(
        self,
        *,
        draft: LocalizedArticle,
        defects: list[dict[str, Any]],
        raw_article_id: int,
    ) -> tuple[LocalizedArticle, list[str]]:
        system = PromptLoader.load("rewriter", self._rewriter_prompt_version)
        clean = _draft_to_clean_dict(draft)
        user = (
            "ORIGINAL DRAFT (JSON):\n"
            f"{json.dumps(clean, ensure_ascii=False, indent=2)}\n\n"
            "DEFECTS LIST (JSON):\n"
            f"{json.dumps(defects, ensure_ascii=False, indent=2)}"
        )

        logger.info(
            "cross_model.rewriter.started",
            raw_article_id=raw_article_id,
            model=self._rewriter_model,
            defects=len(defects),
        )

        response = await self._rewriter_tracker.complete(
            system=system,
            user=user,
            model=self._rewriter_model,
            max_tokens=8192,
            temperature=0.4,
            metadata={"user_id": "rewriter"},
        )

        parsed = self._parse_rewriter_json(response.text)
        article_payload = parsed["corrected_article"]
        corrections_applied = list(parsed.get("corrections_applied") or [])

        # Re-apply bidi wrapping on the rewriter's clean Arabic output.
        for name in _BIDI_FIELDS:
            wrapped = wrap_latin_with_bdi(str(article_payload[name]))
            article_payload[name] = wrapped

        corrected = LocalizedArticle(
            title_darija=str(article_payload["title_darija"]),
            slug=str(article_payload["slug"]),
            excerpt_darija=str(article_payload["excerpt_darija"]),
            content_darija=str(article_payload["content_darija"]),
            meta_title=str(article_payload["meta_title"]),
            meta_description=str(article_payload["meta_description"]),
            categories=list(article_payload["categories"]),
            tags=list(article_payload["tags"]),
            image_prompt=str(article_payload["image_prompt"]),
        )

        logger.info(
            "cross_model.rewriter.completed",
            raw_article_id=raw_article_id,
            duration_ms=response.duration_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=str(response.cost_usd),
            corrections_count=len(corrections_applied),
            wrapped_terms_total=sum(
                count_wrapped_terms(getattr(corrected, f)) for f in _BIDI_FIELDS
            ),
            word_count=corrected.word_count,
        )
        return corrected, corrections_applied

    @staticmethod
    def _parse_rewriter_json(raw_text: str) -> dict[str, Any]:
        cleaned = _strip_json_fence(raw_text)
        try:
            parsed: Any = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIQualityError(
                "Rewriter returned invalid JSON",
                details={"reason": "invalid_json", "error": str(exc)},
            ) from exc

        if not isinstance(parsed, dict) or "corrected_article" not in parsed:
            raise AIQualityError(
                "Rewriter JSON missing 'corrected_article'",
                details={"reason": "missing_corrected_article"},
            )

        article_payload = parsed["corrected_article"]
        if not isinstance(article_payload, dict):
            raise AIQualityError(
                "Rewriter 'corrected_article' must be an object",
                details={"reason": "corrected_article_not_object"},
            )
        missing = [f for f in REQUIRED_FIELDS if f not in article_payload]
        if missing:
            raise AIQualityError(
                "Rewriter 'corrected_article' missing required fields",
                details={"reason": "missing_fields", "missing": missing},
            )
        return parsed
