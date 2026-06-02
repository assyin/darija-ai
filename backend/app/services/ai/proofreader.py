"""AI-powered translation proofreader.

Evaluates a Darija (or French) editorial translation and returns an
editorial score 0-100 plus up to 12 localized fix suggestions the admin
UI presents inline (Grammarly-style). Uses OpenAI's structured-output
mode for reliable JSON parsing. Cached in Redis 24 h by content hash so
re-evaluations on the same text are free.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from openai import AsyncOpenAI
from redis.asyncio import Redis

from app.core.exceptions import AIQualityError, ExternalServiceError
from app.core.logging import get_logger
from app.schemas.proofread import (
    Category,
    Field_,
    Language,
    ProofreadResult,
    ProofreadSuggestion,
    Severity,
)

logger = get_logger("services.ai.proofreader")

PROMPT_VERSION = "v1"
CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 h

_VALID_SEVERITIES: set[Severity] = {"low", "medium", "high"}
_VALID_CATEGORIES: set[Category] = {"grammar", "naturalness", "clarity", "consistency"}


def _system_prompt(lang: Language, field: Field_) -> str:
    """Return the system prompt for a (language, field) combination.

    Darija and French use different guidance because the linguistic
    constraints diverge. ``field`` lets us soften the score for short
    inputs (titles can't be evaluated like full bodies).
    """
    common_rules = (
        "Score 0-100. Be generous: 80+ = publishable; 60-79 = minor fixes; "
        "<60 = significant rewrite. Suggestions: max 8, highest impact first. "
        "Each suggestion's 'original' MUST be an EXACT contiguous substring "
        "copy-pasted character-for-character from the input — INCLUDING "
        "Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩) vs Latin digits (0123456789), "
        "punctuation, white-space, line breaks, and any inline markup like "
        "<bdi>…</bdi>. Do NOT paraphrase, normalize, translate, or shorten. "
        "If you cannot find an exact substring that needs fixing, skip the "
        "suggestion. 'suggestion' is the proposed replacement (may be empty "
        "to indicate deletion). 'reason' is ONE short sentence in French."
    )

    if lang == "darija":
        guidance = (
            "You are the senior editor of TitritAI, a Moroccan tech magazine "
            "publishing in Moroccan Darija (Darija marocaine, not MSA). Your "
            "job is to evaluate a translation for naturalness, clarity, "
            "grammar, and consistency.\n\n"
            "Darija specifics:\n"
            "- Darija is informal urban Moroccan Arabic, NOT MSA (Modern "
            "Standard Arabic). MSA wording is a downgrade.\n"
            "- Loan words from French/English are NATURAL when widely used: "
            "chatbot, AI, prompt, dataset, GPU, API, software, smartphone, "
            "etc. Don't flag them.\n"
            "- Technical terms wrapped in <bdi>...</bdi> are intentional and "
            "correct — never flag those wrappers.\n"
            "- Markdown syntax (##, **, lists) is meta — never flag it.\n"
            "- Honor Moroccan dialectal verb forms (كنخدم, غادي, دابا, بزاف, "
            "بحال, هاد) rather than MSA equivalents.\n"
            "- Numbers written in Arabic or Western digits are both fine.\n\n"
        )
    else:  # french
        guidance = (
            "You are the senior editor of TitritAI, a Moroccan tech magazine. "
            "You are evaluating the French version of a translation for "
            "naturalness, clarity, grammar, and consistency.\n\n"
            "French specifics:\n"
            "- Modern, accessible French (not academic). Tech-savvy audience.\n"
            "- Anglicisms widely used in French tech are fine (chatbot, "
            "prompt, dataset, etc.).\n"
            "- Markdown syntax (##, **, lists) is meta — never flag it.\n"
            "- Honor French typographic spaces around ; : ! ? and «  » where "
            "they apply.\n\n"
        )

    field_note = {
        "title": (
            "This is an article TITLE — short (≤ 70 chars). Score it on "
            "punch, clarity, and how well it would perform in a feed."
        ),
        "excerpt": (
            "This is the article EXCERPT — 1-2 sentences (≤ 160 chars). "
            "Score it on hook, clarity, and how well it sets up the body."
        ),
        "body": (
            "This is the full article BODY in Markdown. Score it on overall translation quality."
        ),
    }[field]

    return (
        guidance
        + field_note
        + "\n\n"
        + common_rules
        + "\n\nReturn STRICT JSON matching the schema. No prose, no markdown."
    )


def _user_prompt(text: str) -> str:
    return f"Evaluate this text and return JSON only:\n\n---\n{text}\n---"


# Schema passed to OpenAI structured-output (json_schema response_format)
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["score", "summary", "suggestions"],
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string", "maxLength": 400},
        "suggestions": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "original",
                    "suggestion",
                    "reason",
                    "severity",
                    "category",
                ],
                "properties": {
                    "original": {"type": "string", "maxLength": 300},
                    "suggestion": {"type": "string", "maxLength": 300},
                    "reason": {"type": "string", "maxLength": 240},
                    "severity": {"enum": ["low", "medium", "high"]},
                    "category": {
                        "enum": [
                            "grammar",
                            "naturalness",
                            "clarity",
                            "consistency",
                        ]
                    },
                },
            },
        },
    },
}


def _cache_key(model: str, lang: Language, field: Field_, text: str) -> str:
    digest = hashlib.sha256(f"{PROMPT_VERSION}\n{lang}\n{field}\n{text}".encode()).hexdigest()[:32]
    return f"proofread:{model}:{digest}"


class Proofreader:
    """OpenAI-backed proofreader with Redis caching."""

    def __init__(
        self,
        *,
        api_key: str,
        redis_client: Redis,
        model: str = "gpt-4o-mini",
    ) -> None:
        if not api_key:
            raise ExternalServiceError(
                "OpenAI API key not configured",
                details={"setting": "OPENAI_API_KEY"},
            )
        self._client = AsyncOpenAI(api_key=api_key)
        self._redis = redis_client
        self._model = model

    async def proofread(
        self,
        *,
        text: str,
        lang: Language,
        field: Field_,
    ) -> ProofreadResult:
        key = _cache_key(self._model, lang, field, text)
        cached_raw = await self._redis.get(key)
        if cached_raw is not None:
            try:
                payload = json.loads(cached_raw)
                logger.info(
                    "proofreader.cache_hit",
                    key=key,
                    score=payload.get("score"),
                )
                return ProofreadResult(
                    **payload,
                    lang=lang,
                    field=field,
                    model=self._model,
                    cached=True,
                )
            except Exception:
                # Corrupted cache entry — fall through and recompute.
                await self._redis.delete(key)

        start = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=0.2,
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": _system_prompt(lang, field)},
                    {"role": "user", "content": _user_prompt(text)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "proofread_result",
                        "schema": _RESPONSE_SCHEMA,
                        "strict": True,
                    },
                },
            )
        except Exception as exc:
            logger.exception(
                "proofreader.openai_failed",
                lang=lang,
                field=field,
                error=str(exc),
            )
            raise ExternalServiceError(
                f"OpenAI proofread failed: {exc.__class__.__name__}",
                details={"error": str(exc)},
            ) from exc

        duration_ms = int((time.perf_counter() - start) * 1000)
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise AIQualityError("OpenAI returned empty content", details={})

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIQualityError(
                "OpenAI returned non-JSON output",
                details={"error": str(exc), "preview": content[:200]},
            ) from exc

        suggestions = [
            ProofreadSuggestion(
                original=str(s.get("original", "")),
                suggestion=str(s.get("suggestion", "")),
                reason=str(s.get("reason", "")),
                severity=(
                    s.get("severity") if s.get("severity") in _VALID_SEVERITIES else "medium"
                ),
                category=(
                    s.get("category") if s.get("category") in _VALID_CATEGORIES else "naturalness"
                ),
            )
            for s in parsed.get("suggestions", [])
            if s.get("original")
        ]
        score = int(parsed.get("score", 0))
        summary = str(parsed.get("summary", ""))

        result = ProofreadResult(
            score=max(0, min(100, score)),
            summary=summary,
            suggestions=suggestions,
            lang=lang,
            field=field,
            model=self._model,
            cached=False,
        )

        # Persist to cache. Omit `cached` from the stored payload so a hit can
        # set it to True on retrieve.
        cache_payload = json.dumps(
            {
                "score": result.score,
                "summary": result.summary,
                "suggestions": [s.model_dump() for s in result.suggestions],
            },
            ensure_ascii=False,
        )
        await self._redis.set(key, cache_payload, ex=CACHE_TTL_SECONDS)

        logger.info(
            "proofreader.completed",
            model=self._model,
            lang=lang,
            field=field,
            score=result.score,
            num_suggestions=len(result.suggestions),
            duration_ms=duration_ms,
            tokens_used=getattr(response.usage, "total_tokens", None),
        )
        return result
