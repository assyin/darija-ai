from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.exceptions import AIQualityError
from app.core.logging import get_logger
from app.services.ai.bidi import (
    count_wrapped_terms,
    strip_bdi_tags,
    wrap_latin_with_bdi,
)
from app.services.ai.llm_provider import LLMProvider
from app.services.ai.localizer import REQUIRED_FIELDS, LocalizedArticle
from app.services.ai.prompt_loader import PromptLoader

logger = get_logger("services.ai.critic_editor")

_BIDI_FIELDS: tuple[str, ...] = (
    "title_darija",
    "excerpt_darija",
    "content_darija",
    "meta_title",
    "meta_description",
)
_ORIGINAL_SOURCE_PREVIEW_CHARS = 2000


@dataclass(frozen=True)
class CriticEditorResult:
    corrected_article: LocalizedArticle
    corrections_made: list[str] = field(default_factory=list)
    corrections_count: int = 0
    cost_usd: Decimal = Decimal("0")
    duration_ms: int = 0
    model: str = ""


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
    """Strip <bdi> tags from textual fields so the critic edits clean Arabic."""
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


class CriticEditor:
    def __init__(
        self,
        provider: LLMProvider,
        prompt_version: str = "v1",
        model: str | None = None,
    ):
        self._provider = provider
        self._prompt_version = prompt_version
        self._model = model or provider.default_model

    async def review(self, draft: LocalizedArticle, original_source: str) -> CriticEditorResult:
        system = PromptLoader.load("critic_editor", self._prompt_version)

        clean_draft = _draft_to_clean_dict(draft)
        user = (
            "DRAFT (JSON):\n"
            f"{json.dumps(clean_draft, ensure_ascii=False, indent=2)}\n\n"
            "ORIGINAL SOURCE (for facts):\n"
            f"{original_source[:_ORIGINAL_SOURCE_PREVIEW_CHARS]}"
        )

        logger.info(
            "critic_editor.started",
            model=self._model,
            prompt_version=self._prompt_version,
        )

        start = time.perf_counter()
        response = await self._provider.complete(
            system=system,
            user=user,
            model=self._model,
            max_tokens=8192,
            metadata={"user_id": "critic"},
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        parsed = self._parse(response.text)
        article_payload = parsed["corrected_article"]
        corrections_made = list(parsed.get("corrections_made") or [])
        try:
            corrections_count = int(parsed.get("corrections_count", 0))
        except (TypeError, ValueError):
            corrections_count = len(corrections_made)

        wrapped_total = 0
        for name in _BIDI_FIELDS:
            wrapped = wrap_latin_with_bdi(str(article_payload[name]))
            wrapped_total += count_wrapped_terms(wrapped)
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
            "critic_editor.completed",
            model=self._model,
            duration_ms=duration_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=str(response.cost_usd),
            corrections_count=corrections_count,
            num_wrapped_terms=wrapped_total,
            word_count=corrected.word_count,
        )

        return CriticEditorResult(
            corrected_article=corrected,
            corrections_made=corrections_made,
            corrections_count=corrections_count,
            cost_usd=response.cost_usd,
            duration_ms=duration_ms,
            model=self._model,
        )

    def _parse(self, raw_text: str) -> dict[str, Any]:
        cleaned = _strip_json_fence(raw_text)
        try:
            parsed: Any = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "critic_editor.parse_failed",
                error=str(exc),
                response_preview=cleaned[:300],
            )
            raise AIQualityError(
                "Critic returned invalid JSON",
                details={"reason": "invalid_json", "error": str(exc)},
            ) from exc

        if not isinstance(parsed, dict) or "corrected_article" not in parsed:
            logger.error(
                "critic_editor.validation_failed",
                reason="missing_corrected_article",
                response_preview=cleaned[:300],
            )
            raise AIQualityError(
                "Critic JSON missing 'corrected_article'",
                details={"reason": "missing_corrected_article"},
            )

        article_payload = parsed["corrected_article"]
        if not isinstance(article_payload, dict):
            raise AIQualityError(
                "Critic 'corrected_article' must be an object",
                details={"reason": "corrected_article_not_object"},
            )
        missing = [f for f in REQUIRED_FIELDS if f not in article_payload]
        if missing:
            logger.error(
                "critic_editor.validation_failed",
                reason="missing_fields",
                missing=missing,
            )
            raise AIQualityError(
                "Critic 'corrected_article' missing required fields",
                details={"reason": "missing_fields", "missing": missing},
            )
        return parsed
