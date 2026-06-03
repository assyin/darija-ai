"""Darija → French editorial translator.

Wraps the ``ClaudeClient`` with the ``translator_darija_to_fr_v1`` system
prompt and a Redis cache (30 days, keyed by content hash) so re-running on
the same Darija text is free. Returns a structured ``TranslateToFrenchResult``
with the 5 French fields the admin form expects.

Used by the ``POST /admin/articles/{id}/translate-to-fr`` endpoint when the
editor clicks the "Traduire en français" button.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from redis.asyncio import Redis

from app.core.exceptions import AIQualityError
from app.core.logging import get_logger
from app.schemas.translate import TranslateToFrenchResult
from app.services.ai.claude_client import ClaudeClient

logger = get_logger("services.ai.translator")

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / "translator_darija_to_fr_v1.md"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

_REQUIRED_FIELDS = (
    "title_fr",
    "excerpt_fr",
    "content_fr",
    "meta_title_fr",
    "meta_description_fr",
)


def _cache_key(model: str, payload: dict[str, str]) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(f"{PROMPT_VERSION}\n{blob}".encode()).hexdigest()[:32]
    return f"translate:fr:{model}:{digest}"


def _strip_json_fences(text: str) -> str:
    """Some models wrap JSON in ```json ... ``` even when told not to."""
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", cleaned)
    if fence:
        return fence.group(1).strip()
    return cleaned


class Translator:
    """Darija → French translator with Redis caching."""

    def __init__(self, *, claude: ClaudeClient, redis_client: Redis) -> None:
        self._claude = claude
        self._redis = redis_client
        self._system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def translate(
        self,
        *,
        title_darija: str,
        excerpt_darija: str,
        content_darija: str,
        meta_title: str | None,
        meta_description: str | None,
    ) -> TranslateToFrenchResult:
        payload = {
            "title": title_darija,
            "excerpt": excerpt_darija,
            "content": content_darija,
            "meta_title": meta_title or "",
            "meta_description": meta_description or "",
        }
        model = self._claude.default_model
        key = _cache_key(model, payload)

        cached_raw = await self._redis.get(key)
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
                logger.info("translator.cache_hit", key=key)
                return TranslateToFrenchResult(**cached, model=model, cached=True, duration_ms=0)
            except Exception:
                await self._redis.delete(key)

        user_prompt = _build_user_prompt(payload)
        start = time.perf_counter()
        response = await self._claude.complete(
            system=self._system_prompt,
            user=user_prompt,
            # Editorial translation: low temperature for stability.
            temperature=0.4,
            # Bodies can be ~3000 words → ~9000 tokens output; budget headroom.
            max_tokens=8192,
            metadata={"user_id": "translator"},
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        cleaned = _strip_json_fences(response.text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.exception(
                "translator.bad_json",
                preview=cleaned[:200],
                error=str(exc),
            )
            raise AIQualityError(
                "Translator returned non-JSON output",
                details={"error": str(exc), "preview": cleaned[:200]},
            ) from exc

        missing = [f for f in _REQUIRED_FIELDS if f not in data]
        if missing:
            raise AIQualityError(
                f"Translator output missing fields: {missing}",
                details={"missing": missing, "got": list(data.keys())},
            )

        normalized = {f: str(data.get(f, "")) for f in _REQUIRED_FIELDS}
        # Persist *without* model/cached/duration_ms (those are per-call).
        await self._redis.set(
            key,
            json.dumps(normalized, ensure_ascii=False),
            ex=CACHE_TTL_SECONDS,
        )

        logger.info(
            "translator.completed",
            model=model,
            duration_ms=duration_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=str(response.cost_usd),
            content_chars=len(normalized["content_fr"]),
        )
        return TranslateToFrenchResult(
            **normalized,
            model=model,
            cached=False,
            duration_ms=duration_ms,
        )


def _build_user_prompt(payload: dict[str, str]) -> str:
    return (
        "Translate this editorial article from Moroccan Darija into modern French.\n"
        "Return ONLY a JSON object matching the schema in the system prompt.\n\n"
        f"### Title (Darija)\n{payload['title']}\n\n"
        f"### Excerpt (Darija)\n{payload['excerpt']}\n\n"
        f"### Body (Darija, Markdown)\n{payload['content']}\n\n"
        f"### Existing meta_title (Darija — may be empty)\n{payload['meta_title']}\n\n"
        f"### Existing meta_description (Darija — may be empty)\n{payload['meta_description']}"
    )
