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

PROMPT_VERSION = "v4"
CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 h

# Weighted-aggregation parameters (v3 aggregation, paired with v4 prompt).
# Naturalness has been the bottleneck dimension across every audit we ran;
# weighting it heaviest means a Localizer change that lifts naturalness moves
# the headline score the most. Sum of weights == 1.0; integer result.
_NATURALNESS_WEIGHT = 0.40
_CLARITY_WEIGHT = 0.25
_CONSISTENCY_WEIGHT = 0.20
_GRAMMAR_WEIGHT = 0.15

_VALID_SEVERITIES: set[Severity] = {"low", "medium", "high"}
_VALID_CATEGORIES: set[Category] = {"grammar", "naturalness", "clarity", "consistency"}


def _system_prompt(lang: Language, field: Field_) -> str:
    """Return the system prompt for a (language, field) combination.

    Darija and French use different guidance because the linguistic
    constraints diverge. ``field`` lets us soften the score for short
    inputs (titles can't be evaluated like full bodies).
    """
    common_rules = (
        "═══════════════════════════════════════════════════════════════════\n"
        "ANTI-ANCHORING — read this BEFORE evaluating\n"
        "═══════════════════════════════════════════════════════════════════\n\n"
        "Past evaluators of this corpus collapsed every article into the SAME\n"
        "score template (grammar=85, naturalness=75, clarity=80, consistency=80).\n"
        "That template is the WORST possible output — it tells the editor\n"
        "nothing about which articles to publish first. Your evaluation has\n"
        "FAILED its purpose if your four sub-scores cluster in a single\n"
        "5-point band for every article.\n\n"
        "You MUST satisfy these constraints or the evaluation is defective:\n\n"
        "  R1. EXPLICIT SPREAD — at least TWO of the four sub-scores MUST\n"
        "      differ from each other by 5+ points. The literal quadruple\n"
        "      (85, 75, 80, 80) or (85, 75, 80, 85) is BANNED — if your\n"
        "      honest evaluation lands there, perturb ONE sub-score by ±5\n"
        "      based on the strongest signal in the text.\n\n"
        "  R2. USE THE FULL 0-100 RANGE — expected corpus distribution:\n"
        "         < 50      :  ~5%   (rewrite from scratch)\n"
        "         50-64     : ~15%   (heavy rework)\n"
        "         65-74     : ~30%   (rough, multiple passes needed)\n"
        "         75-84     : ~30%   (acceptable, light edits)\n"
        "         85-92     : ~15%   (strong, minimal polish)\n"
        "         93+       :  ~5%   (excellent, publishable as-is)\n"
        "      If you return 75-80 for everything, you are anchoring. Push\n"
        "      yourself to discriminate.\n\n"
        "  R3. EVIDENCE-DRIVEN — each sub-score MUST be tied to a SPECIFIC\n"
        "      observation in the text. If you cannot quote the exact phrase\n"
        "      that justifies the score, the score is invalid.\n\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "CALIBRATION ANCHORS — three Darija snippets with their scores\n"
        "═══════════════════════════════════════════════════════════════════\n\n"
        "EXCELLENT (grammar=95, naturalness=92, clarity=90, consistency=92):\n"
        '  "OpenAI طلقات ChatGPT-5 الأسبوع لي فات. من نهار الإطلاق، الناس\n'
        "   فالويب كيقولو بللي الموديل بان مختلف بزاف على القديم. الفرق\n"
        '   الكبير؟ ChatGPT-5 كيفهم السياق الطويل أحسن ولا كيخلط."\n'
        "  → Verb early. Native idioms (فالويب, بزاف, ولا). Short sentences.\n"
        "    Zero French calque. Tech terms in Latin script.\n\n"
        "MEDIUM (grammar=85, naturalness=72, clarity=80, consistency=78):\n"
        '  "الشركة الفرنسية ديال AI Mistral، لي كاتعتبر واحدة من أكبر الشركات\n'
        "   الناشئة فأوروبا والمعروفة بالموديل ديالها لي كاتسما Mistral Large،\n"
        '   أعلنات اليوم على round ديال تمويل ضخم بمناسبة عيد السنة."\n'
        "  → Subject 18 words before the verb (FR structure preserved).\n"
        "    'كاتعتبر' / 'بمناسبة' are calques. Sub-scores SPREAD 13 points.\n\n"
        "WEAK (grammar=75, naturalness=55, clarity=62, consistency=58):\n"
        '  "في إطار التحول الرقمي ديال القطاع، الشركة قامات بإطلاق منصة جديدة\n'
        "   كاتسمح للمستخدمين بالاستفادة من خدمات الذكاء الاصطناعي بشكل أكثر\n"
        '   فعالية و في إطار سياسة الانفتاح على المنظومة الريادية الوطنية."\n'
        "  → 'في إطار' (x2) literal calque. 'التحول الرقمي' / 'المنظومة\n"
        "    الريادية' are administrative French nouns transliterated.\n"
        "    Reads as press-release translated by a junior. Spread 20 points.\n\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "HEURISTICS for NATURALNESS (the bottleneck dimension)\n"
        "═══════════════════════════════════════════════════════════════════\n\n"
        "Start from a base of 80, then ADJUST:\n\n"
        "  + Native Darija idioms (بحال، فاش، ملي، تما، دابا، شي، عاد)\n"
        "      → +1 per distinct idiom, cap +5\n"
        "  + Verb within first 5 words of the sentence\n"
        "      → +2 if ≥80% of sentences satisfy\n"
        "  + Tech term in Latin script (OpenAI, GPT, API)\n"
        "      → +1 (anti-transliteration signal)\n"
        "  + Punchy sentences (< 15 words avg)\n"
        "      → +2\n\n"
        "  - French connector literal ('في إطار', 'بشكل آخر', 'في الحقيقة',\n"
        "    'بمناسبة', 'علاوة على ذلك')\n"
        "      → -2 per occurrence\n"
        "  - Sentence > 25 words with subordinate clauses\n"
        "      → -3 per occurrence\n"
        "  - Administrative French noun transliterated ('التحول الرقمي',\n"
        "    'المنظومة الريادية', 'الإشكالية', 'الإطار التنظيمي')\n"
        "      → -3 per occurrence\n"
        "  - Subject longer than 7 words before verb\n"
        "      → -1 per occurrence\n\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "SUB-SCORE DEFINITIONS\n"
        "═══════════════════════════════════════════════════════════════════\n\n"
        "  • grammar — verb conjugation, agreement, syntax, punctuation.\n"
        "    Most articles land 75-90 because the generator is competent.\n"
        "    Reserve <70 for visibly broken grammar.\n"
        "  • naturalness — does it read like a Moroccan tech editor wrote\n"
        "    it, or like a translation? MSA disguised as Darija = penalty.\n"
        "    Apply the heuristics above.\n"
        "  • clarity — does each paragraph convey ONE clear idea? Are\n"
        "    technical terms explained on first mention? Is the structure\n"
        "    pyramid-shaped (key info first)?\n"
        "  • consistency — does voice/tone stay even? Are technical terms\n"
        "    rendered the same way throughout (Claude vs كلود)? Is the\n"
        "    audience level stable?\n\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "SCORE FIELD (informational only — server overrides)\n"
        "═══════════════════════════════════════════════════════════════════\n\n"
        "The top-level 'score' you return is informational; the server\n"
        "computes the final headline score from your four sub-scores via a\n"
        "naturalness-weighted average (40% nat, 25% clar, 20% consist,\n"
        "15% gram). Report it anyway for schema compatibility — just be\n"
        "honest about each sub-score and the aggregation will follow.\n\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "SUGGESTIONS\n"
        "═══════════════════════════════════════════════════════════════════\n\n"
        "Max 8, highest-impact first. Each suggestion's 'original' MUST be\n"
        "an EXACT contiguous substring copy-pasted character-for-character\n"
        "from the input — INCLUDING Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩) vs\n"
        "Latin digits (0123456789), punctuation, white-space, line breaks,\n"
        "and any inline markup like <bdi>…</bdi>. Do NOT paraphrase,\n"
        "normalize, translate, or shorten. If you cannot find an exact\n"
        "substring that needs fixing, skip the suggestion. 'suggestion' is\n"
        "the proposed replacement (may be empty for deletion). 'reason' is\n"
        "ONE short sentence in French."
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
        raw_article_id: int | None = None,
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
                raw_article_id=raw_article_id,
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
            raw_article_id=raw_article_id,
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

        # Server is the source of truth for the top-level score. v4 uses a
        # naturalness-weighted average instead of the v2 MIN rule. The MIN
        # rule turned out to be the source of the 85/75/80/80 anchor we
        # diagnosed at length — see docs/DECISIONS.md ADR-005 and the
        # session sandbox runs in 2026-06-07.
        #
        # When all four sub-scores are present, score = weighted average.
        # When a legacy v1/v2 cached entry comes back with no sub-scores,
        # fall back to the model-reported top-level. When nothing is
        # parseable, fall back to 0 to avoid crashing.
        if (
            grammar is not None
            and naturalness is not None
            and clarity is not None
            and consistency is not None
        ):
            weighted = (
                _GRAMMAR_WEIGHT * grammar
                + _NATURALNESS_WEIGHT * naturalness
                + _CLARITY_WEIGHT * clarity
                + _CONSISTENCY_WEIGHT * consistency
            )
            score = round(weighted)
        elif model_score is not None:
            score = model_score
        else:
            score = 0

        if model_score is not None and model_score != score:
            logger.info(
                "proofreader.score_recomputed",
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
