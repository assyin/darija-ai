from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from redis.asyncio import Redis

from app.core.exceptions import AIQualityError
from app.core.logging import get_logger
from app.services.ai.bidi import count_wrapped_terms, wrap_latin_with_bdi
from app.services.ai.llm_provider import LLMProvider
from app.services.ai.prompt_loader import PromptLoader

logger = get_logger("services.ai.localizer")

REQUIRED_FIELDS: tuple[str, ...] = (
    "title_darija",
    "slug",
    "excerpt_darija",
    "content_darija",
    "meta_title",
    "meta_description",
    "categories",
    "tags",
    "image_prompt",
)

WORDS_PER_MINUTE = 200
DEFAULT_CACHE_TTL_SECONDS = 30 * 24 * 3600

# Fields the bidi wrapper applies to. Slug/categories/tags/image_prompt stay raw.
_BIDI_FIELDS: tuple[str, ...] = (
    "title_darija",
    "excerpt_darija",
    "content_darija",
    "meta_title",
    "meta_description",
)


def _strip_json_fence(text: str) -> str:
    """Drop ```json ... ``` or ``` ... ``` wrappers some models emit."""
    s = text.strip()
    if s.startswith("```"):
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1 :]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


@dataclass(frozen=True)
class LocalizedArticle:
    title_darija: str
    slug: str
    excerpt_darija: str
    content_darija: str
    meta_title: str
    meta_description: str
    categories: list[str]
    tags: list[str]
    image_prompt: str
    word_count: int = field(init=False)
    reading_time_minutes: int = field(init=False)

    def __post_init__(self) -> None:
        wc = len(self.content_darija.split())
        rt = max(1, math.ceil(wc / WORDS_PER_MINUTE))
        object.__setattr__(self, "word_count", wc)
        object.__setattr__(self, "reading_time_minutes", rt)


PRODUCTION_MODEL = "claude-haiku-4-5"


class Localizer:
    """End-to-end Darija localization with prompt loading, JSON validation, bidi
    post-processing, and a Redis content-hash cache.

    Production model: Claude Haiku 4.5. All output is reviewed by a human
    editor in the admin panel before publication. Sonnet 4.6 available as
    opt-in for flagship articles by passing ``model="claude-sonnet-4-6"``.

    See ADR-002 in ``docs/DECISIONS.md`` for the rationale (volume, cost,
    human-in-the-loop QA layer).
    """

    def __init__(
        self,
        provider: LLMProvider,
        redis_client: Redis | None = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        prompt_version: str = "v2",
        model: str = PRODUCTION_MODEL,
        bidi_wrap: bool = True,
    ):
        self._provider = provider
        self._redis = redis_client
        self._cache_ttl = cache_ttl_seconds
        self._prompt_version = prompt_version
        self._model = model
        self._bidi_wrap = bidi_wrap

    async def localize(
        self,
        *,
        title: str,
        content: str,
        source_name: str,
        raw_article_id: int,
    ) -> LocalizedArticle:
        cache_key = self._build_cache_key(title=title, content=content)
        cache_key_prefix = cache_key.rsplit(":", 1)[0] + ":..."

        if self._redis is not None:
            cached = await self._read_cache(cache_key)
            if cached is not None:
                logger.info(
                    "localizer.cache_hit",
                    raw_article_id=raw_article_id,
                    cache_key_prefix=cache_key_prefix,
                )
                return cached
            logger.info(
                "localizer.cache_miss",
                raw_article_id=raw_article_id,
                cache_key_prefix=cache_key_prefix,
            )

        system = PromptLoader.load("localizer", self._prompt_version)
        user = self._build_user_message(title=title, content=content, source_name=source_name)

        logger.info(
            "localizer.started",
            raw_article_id=raw_article_id,
            source_name=source_name,
            prompt_version=self._prompt_version,
            model=self._model,
            input_chars=len(content),
        )

        response = await self._provider.complete(
            system=system,
            user=user,
            model=self._model,
            max_tokens=8192,
            metadata={"user_id": "system"},
            # The localizer_v3 system prompt is ~15.6k tokens — the heaviest
            # repeated input we send to Claude. Caching it cuts the input
            # bill ~90% on every call after the first within the 5-min window.
            cache_system=True,
        )

        parsed = self._parse_and_validate(response.text, raw_article_id)
        fields = {key: parsed[key] for key in REQUIRED_FIELDS}

        if self._bidi_wrap:
            wrapped_total = 0
            for name in _BIDI_FIELDS:
                wrapped = wrap_latin_with_bdi(str(fields[name]))
                wrapped_total += count_wrapped_terms(wrapped)
                fields[name] = wrapped
            logger.info(
                "localizer.bidi_wrapped",
                raw_article_id=raw_article_id,
                num_wrapped_terms=wrapped_total,
            )

        article = LocalizedArticle(
            title_darija=str(fields["title_darija"]),
            slug=str(fields["slug"]),
            excerpt_darija=str(fields["excerpt_darija"]),
            content_darija=str(fields["content_darija"]),
            meta_title=str(fields["meta_title"]),
            meta_description=str(fields["meta_description"]),
            categories=list(fields["categories"]),
            tags=list(fields["tags"]),
            image_prompt=str(fields["image_prompt"]),
        )

        logger.info(
            "localizer.completed",
            raw_article_id=raw_article_id,
            duration_ms=response.duration_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=str(response.cost_usd),
            word_count=article.word_count,
            reading_time_minutes=article.reading_time_minutes,
        )

        if self._redis is not None:
            await self._write_cache(cache_key, article)

        return article

    def _parse_and_validate(self, raw_text: str, raw_article_id: int) -> dict[str, Any]:
        cleaned = _strip_json_fence(raw_text)
        try:
            parsed: Any = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "localizer.parse_failed",
                raw_article_id=raw_article_id,
                error=str(exc),
                response_preview=raw_text[:300],
            )
            raise AIQualityError(
                "Localizer returned invalid JSON",
                details={
                    "reason": "invalid_json",
                    "raw_article_id": raw_article_id,
                    "error": str(exc),
                },
            ) from exc

        if not isinstance(parsed, dict):
            logger.error(
                "localizer.validation_failed",
                raw_article_id=raw_article_id,
                reason="not_an_object",
                response_preview=raw_text[:300],
            )
            raise AIQualityError(
                "Localizer JSON must be an object",
                details={
                    "reason": "not_an_object",
                    "raw_article_id": raw_article_id,
                },
            )

        if parsed.get("reject") is True:
            reason = parsed.get("reason", "rejected_by_model")
            logger.warning(
                "localizer.rejected_by_model",
                raw_article_id=raw_article_id,
                reason=reason,
            )
            raise AIQualityError(
                "Model rejected the source article",
                details={
                    "reason": "rejected_by_model",
                    "raw_article_id": raw_article_id,
                    "model_reason": reason,
                },
            )

        missing = [f for f in REQUIRED_FIELDS if f not in parsed]
        if missing:
            logger.error(
                "localizer.validation_failed",
                raw_article_id=raw_article_id,
                reason="missing_fields",
                missing=missing,
            )
            raise AIQualityError(
                "Localizer JSON missing required fields",
                details={
                    "reason": "missing_fields",
                    "raw_article_id": raw_article_id,
                    "missing": missing,
                },
            )
        return parsed

    def _build_cache_key(self, *, title: str, content: str) -> str:
        prompt_hash = PromptLoader.hash("localizer", self._prompt_version)[:16]
        content_hash = hashlib.sha256(f"{title}|{content}".encode()).hexdigest()[:16]
        return (
            f"localizer:{self._provider.provider_name}:{self._model}:{prompt_hash}:{content_hash}"
        )

    async def _read_cache(self, key: str) -> LocalizedArticle | None:
        assert self._redis is not None
        try:
            payload = await self._redis.get(key)
        except Exception:
            logger.exception("localizer.cache_read_failed", cache_key=key)
            return None
        if payload is None:
            return None
        try:
            data = json.loads(payload)
            return LocalizedArticle(
                title_darija=data["title_darija"],
                slug=data["slug"],
                excerpt_darija=data["excerpt_darija"],
                content_darija=data["content_darija"],
                meta_title=data["meta_title"],
                meta_description=data["meta_description"],
                categories=list(data["categories"]),
                tags=list(data["tags"]),
                image_prompt=data["image_prompt"],
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.exception("localizer.cache_deserialize_failed", cache_key=key)
            return None

    async def _write_cache(self, key: str, article: LocalizedArticle) -> None:
        assert self._redis is not None
        payload = asdict(article)
        # Drop computed fields — they re-derive from content_darija on load.
        payload.pop("word_count", None)
        payload.pop("reading_time_minutes", None)
        try:
            await self._redis.set(key, json.dumps(payload), ex=self._cache_ttl)
        except Exception:
            logger.exception("localizer.cache_write_failed", cache_key=key)

    @staticmethod
    def _build_user_message(*, title: str, content: str, source_name: str) -> str:
        return (
            f"<TITLE>\n{title}\n</TITLE>\n\n"
            f"<SOURCE>\n{source_name}\n</SOURCE>\n\n"
            f"<CONTENT>\n{content}\n</CONTENT>"
        )
