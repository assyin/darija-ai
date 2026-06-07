"""Direct EN → French editorial localizer.

Replaces the deprecated ``translator.py`` cascade (Darija → French). The
French now reads cleaner because it never inherits Darija-shaped phrasing —
the model writes the French version directly from the original English
article. See ``prompts/localizer_fr_v1.md`` for the full editorial brief
(neutral 3rd-person voice, francophonie-wide audience: Morocco, Francophone
Africa, Belgium, Switzerland, Quebec, France).

Output schema is identical to ``Translator.translate`` — same
``TranslateToFrenchResult`` shape, same 5 fields, same caller code — so the
swap inside ``article_processor.py`` is just a name change.

Cached in Redis 30 days, keyed by content hash + prompt version, so any
re-publishing flow on the same source article costs nothing.
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
from app.services.ai.llm_provider import LLMProvider

logger = get_logger("services.ai.french_localizer")

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / "localizer_fr_v1.md"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days — matches the Darija localizer + translator.

_REQUIRED_FIELDS = (
    "title_fr",
    "excerpt_fr",
    "content_fr",
    "meta_title_fr",
    "meta_description_fr",
)


def _cache_key(model: str, payload: dict[str, str]) -> str:
    """Compose a stable Redis key from prompt version + EN input.

    Including PROMPT_VERSION means a prompt bump (v1 → v2) invalidates every
    cached French output automatically, without a manual flush.
    """
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(f"{PROMPT_VERSION}\n{blob}".encode()).hexdigest()[:32]
    return f"localize:fr:{model}:{digest}"


def _strip_json_fences(text: str) -> str:
    """Strip ```json ... ``` wrappers that some models add despite instructions."""
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", cleaned)
    if fence:
        return fence.group(1).strip()
    return cleaned


class FrenchLocalizer:
    """Generates the 5 French fields of an article directly from the EN source.

    Mirrors the ``Translator`` interface (same return type, same call shape
    from the pipeline) so the pipeline only needs to swap which service it
    calls. Internally, the only differences are:

    - The input is the **raw English article**, not the Darija output
    - The system prompt is ``localizer_fr_v1.md``, which targets the full
      francophonie and forbids over-explanation
    - The Redis namespace is ``localize:fr:`` instead of ``translate:fr:``
      so caches don't collide
    """

    def __init__(self, *, provider: LLMProvider, redis_client: Redis) -> None:
        self._provider = provider
        self._redis = redis_client
        self._system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def localize(
        self,
        *,
        title_en: str,
        content_en: str,
        source_name: str | None = None,
        raw_article_id: int | None = None,
    ) -> TranslateToFrenchResult:
        """Localize an English article into the 5 French fields.

        ``source_name`` rides along into the user prompt to give the model a
        soft attribution cue (Frenchweb vs TechCrunch vs Wamda) — useful when
        the editorial voice should pick up slightly different defaults.
        ``raw_article_id`` flows through to ``ai_logs`` so cost attribution
        is per-article.
        """
        payload = {
            "title": title_en,
            "content": content_en,
            "source": source_name or "",
        }
        model = self._provider.default_model
        key = _cache_key(model, payload)

        cached_raw = await self._redis.get(key)
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
                logger.info("french_localizer.cache_hit", key=key)
                return TranslateToFrenchResult(**cached, model=model, cached=True, duration_ms=0)
            except (json.JSONDecodeError, TypeError, ValueError):
                # Corrupt cache row — evict and re-run upstream.
                await self._redis.delete(key)

        user_prompt = _build_user_prompt(payload)
        start = time.perf_counter()
        # raw_article_id flows into ai_logs through provider metadata so the
        # cost dashboard can attribute spend per article.
        call_metadata: dict[str, str] = {"user_id": "french_localizer"}
        if raw_article_id is not None:
            call_metadata["raw_article_id"] = str(raw_article_id)
        response = await self._provider.complete(
            system=self._system_prompt,
            user=user_prompt,
            # Editorial localization — low temperature, same setting as the
            # legacy translator. Output stays reproducible.
            temperature=0.4,
            # Long-form bodies can reach ~3000 words ≈ 9000 tokens of output.
            max_tokens=8192,
            metadata=call_metadata,
            # The localizer_fr_v1 system prompt sits at ~2.5k tokens — just
            # over Anthropic's 2048-token cache minimum for Haiku. Caching it
            # is a strict win once the second article in a batch hits.
            cache_system=True,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        cleaned = _strip_json_fences(response.text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.exception(
                "french_localizer.bad_json",
                preview=cleaned[:200],
                error=str(exc),
            )
            raise AIQualityError(
                "FrenchLocalizer returned non-JSON output",
                details={"error": str(exc), "preview": cleaned[:200]},
            ) from exc

        missing = [f for f in _REQUIRED_FIELDS if f not in data]
        if missing:
            raise AIQualityError(
                f"FrenchLocalizer output missing fields: {missing}",
                details={"missing": missing, "got": list(data.keys())},
            )

        normalized = {f: str(data.get(f, "")) for f in _REQUIRED_FIELDS}
        # Persist without per-call fields (model/cached/duration_ms) — those
        # belong to the call site, not the cached editorial output.
        await self._redis.set(
            key,
            json.dumps(normalized, ensure_ascii=False),
            ex=CACHE_TTL_SECONDS,
        )

        logger.info(
            "french_localizer.completed",
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
    """Render the user-turn for the model.

    The source name (when known) is included as soft context. The model is
    instructed in the system prompt to ignore it for editorial decisions
    unless it carries genuine signal — we surface it here in case future
    versions want to lean on it.
    """
    source_block = f"### Source\n{payload['source']}\n\n" if payload["source"] else ""
    return (
        "Localize this English tech article into French for TitritAI.\n"
        "Follow the editorial brief in the system prompt. Return ONLY a JSON "
        "object matching the documented schema.\n\n"
        f"{source_block}"
        f"### Title (English)\n{payload['title']}\n\n"
        f"### Body (English, Markdown or plain text)\n{payload['content']}"
    )
