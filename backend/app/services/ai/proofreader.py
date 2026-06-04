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
from decimal import Decimal
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
from app.services.ai.ai_logging import persist_ai_log
from app.services.ai.pricing import compute_cost

logger = get_logger("services.ai.proofreader")

PROMPT_VERSION = "v2"
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
        "Evaluate FOUR DIMENSIONS INDEPENDENTLY, on 0-100 each. Be PRECISE, not "
        "generous. Distinguish 82 from 88. Do NOT anchor to a 'publishable' "
        "threshold — the threshold is computed downstream.\n\n"
        "Calibration (apply per dimension):\n"
        "  • 90-100 = excellent, professional editor would not change anything.\n"
        "  • 80-89 = strong, only cosmetic polish would improve it.\n"
        "  • 70-79 = solid but has at least 2-3 concrete issues that the editor "
        "should fix before publishing.\n"
        "  • 60-69 = noticeable issues; needs a thorough pass.\n"
        "  • 50-59 = weak; multiple paragraphs need rework.\n"
        "  • <50 = poor; rewrite from scratch.\n\n"
        "Sub-scores (be specific, do not copy values across dimensions):\n"
        "  • grammar — verb conjugation, agreement, syntax, punctuation.\n"
        "  • naturalness — does it read like a Moroccan tech editor wrote it, "
        "or like a translation? MSA disguised as Darija = penalty.\n"
        "  • clarity — does each sentence convey ONE clear idea? Are technical "
        "terms explained on first mention? Is the structure logical?\n"
        "  • consistency — does the voice/tone stay even? Are technical terms "
        "rendered the same way throughout? Is the audience-level stable?\n\n"
        "Distribute the four scores honestly. It is normal for grammar to be "
        "85 while naturalness is 72 — that is exactly the signal we want. "
        "DO NOT collapse all four to the same number.\n\n"
        "Top-level 'score' MUST be the MINIMUM of the four sub-scores — the "
        "worst dimension dominates. (Server will recompute and reject the "
        "response if min(sub-scores) ≠ score.)\n\n"
        "Suggestions: max 8, highest-impact first. Each suggestion's "
        "'original' MUST be an EXACT contiguous substring copy-pasted "
        "character-for-character from the input — INCLUDING Arabic-Indic "
        "digits (٠١٢٣٤٥٦٧٨٩) vs Latin digits (0123456789), punctuation, "
        "white-space, line breaks, and any inline markup like <bdi>…</bdi>. "
        "Do NOT paraphrase, normalize, translate, or shorten. If you cannot "
        "find an exact substring that needs fixing, skip the suggestion. "
        "'suggestion' is the proposed replacement (may be empty to indicate "
        "deletion). 'reason' is ONE short sentence in French."
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


# Schema passed to OpenAI structured-output (json_schema response_format).
# v2: the four sub-scores are required; the top-level `score` MUST equal the
# minimum of the four (server validates and re-derives if the model drifts).
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "grammar_score",
        "naturalness_score",
        "clarity_score",
        "consistency_score",
        "score",
        "summary",
        "suggestions",
    ],
    "properties": {
        "grammar_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "naturalness_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "clarity_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "consistency_score": {"type": "integer", "minimum": 0, "maximum": 100},
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
            # Record the failed attempt so cost dashboards aren't blind to
            # outages. duration_ms / tokens are unknown on failure.
            await persist_ai_log(
                provider="openai",
                model=self._model,
                success=False,
                cost_usd=Decimal("0"),
                error=str(exc),
            )
            raise ExternalServiceError(
                f"OpenAI proofread failed: {exc.__class__.__name__}",
                details={"error": str(exc)},
            ) from exc

        duration_ms = int((time.perf_counter() - start) * 1000)
        # Record the successful call — Proofreader bypasses OpenAIClient so it
        # needs to log directly. Tokens come from the SDK's usage block.
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        await persist_ai_log(
            provider="openai",
            model=self._model,
            success=True,
            cost_usd=compute_cost(self._model, input_tokens, output_tokens),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
        )
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

        # v2: pull the four sub-scores. If the model dropped any of them
        # (older cached structure, partial response), they default to None
        # and we fall back to the legacy single-score path.
        def _clamp(v: object) -> int | None:
            if v is None:
                return None
            try:
                # int() accepts str | bytes | SupportsInt; cast keeps mypy honest
                # while letting bad values fall to the except below.
                n: int = int(v)  # type: ignore[call-overload]
            except (TypeError, ValueError):
                return None
            return max(0, min(100, n))

        grammar = _clamp(parsed.get("grammar_score"))
        naturalness = _clamp(parsed.get("naturalness_score"))
        clarity = _clamp(parsed.get("clarity_score"))
        consistency = _clamp(parsed.get("consistency_score"))
        model_score = _clamp(parsed.get("score"))
        summary = str(parsed.get("summary", ""))

        # Server is the source of truth for the top-level score: take the
        # MIN of the populated sub-scores. If none arrived (degenerate v1
        # response), fall back to whatever the model returned.
        sub_scores = [s for s in (grammar, naturalness, clarity, consistency) if s is not None]
        if sub_scores:
            score = min(sub_scores)
        elif model_score is not None:
            score = model_score
        else:
            score = 0

        if model_score is not None and sub_scores and model_score != score:
            logger.warning(
                "proofreader.score_corrected",
                model=self._model,
                lang=lang,
                field=field,
                model_score=model_score,
                derived_score=score,
                grammar=grammar,
                naturalness=naturalness,
                clarity=clarity,
                consistency=consistency,
            )

        result = ProofreadResult(
            score=score,
            grammar_score=grammar,
            naturalness_score=naturalness,
            clarity_score=clarity,
            consistency_score=consistency,
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
                "grammar_score": result.grammar_score,
                "naturalness_score": result.naturalness_score,
                "clarity_score": result.clarity_score,
                "consistency_score": result.consistency_score,
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
            grammar=grammar,
            naturalness=naturalness,
            clarity=clarity,
            consistency=consistency,
            num_suggestions=len(result.suggestions),
            duration_ms=duration_ms,
            tokens_used=getattr(response.usage, "total_tokens", None),
        )
        return result
