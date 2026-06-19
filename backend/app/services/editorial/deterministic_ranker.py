"""Deterministic editorial ranker (ERE MVP v1.1) — pure scoring, no I/O.

Step 3 of the ERE rollout: ONLY the scoring logic. No DB, no flags, no job, no
pipeline wiring, no LLM. Every function is pure and deterministic — same input
→ same output — so it is fully unit-testable and reproducible.

Score /100 (importance is the DOMINANT signal, per spec v1.1):

    importance 0-35 · relevance 0-22 · MENA 0-16 · source 0-15 · freshness 0-12

`importance` is a composite (event-type + business magnitude + major actors) so
that an *important* article from a weak source can outrank a *banal* article
from a strong source. Source quality is deliberately a SUPPORT signal (0-15).

Lexicons are bilingual (EN + FR) because raw articles arrive in the source's
language. Text is NFKD-normalized (accent-stripped, lower-cased) so accented FR
terms ("lève", "Médias") match accent-free, lower-case patterns.

Nothing here reads config, the DB, or `datetime.now()`: callers pass the source
tier map, the reference `now`, and the score threshold explicitly.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# --- Signal caps (sum = 100) ---
_CAP_IMPORTANCE = 35
_CAP_RELEVANCE = 22
_CAP_MENA = 16
_CAP_SOURCE = 15
_CAP_FRESHNESS = 12

# Source tier → weight. Support signal: max (15) < importance cap (35) by design.
_TIER_WEIGHTS: dict[str, int] = {"A": _CAP_SOURCE, "B": 10, "C": 5}
_UNKNOWN_TIER_WEIGHT = 4

# Freshness decay window (hours).
_FRESH_FULL_HOURS = 6.0
_FRESH_ZERO_HOURS = 48.0


def _normalize(text: str) -> str:
    """Lower-case + NFKD strip accents → patterns can be plain lower-case ASCII."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Lexicons / patterns — lower-case, accent-free (matched on normalized text).
# Bilingual EN + FR. Word-boundary anchored.
# ---------------------------------------------------------------------------

# Importance sub-signal 1 — event type (0-15 major / 8 partnership / 0).
_MAJOR_EVENT_RE = re.compile(
    r"\b(?:launch|launches|unveil|unveils|releases?|announces?|debut|lance|"
    r"devoile|presente|annonce|acquires?|acquisition|merger|buyout|rachat|"
    r"rachete|fusion|acquiert|raises?|funding|series\s+[a-e]|valuation|leve|"
    r"levee\s+de\s+fonds|valorisation|regulation|lawsuit|sues|ban|"
    r"executive\s+order|interdit|poursuite|proces|breakthrough|outperforms|"
    r"state-of-the-art|record|percee)\b"
)
_PARTNERSHIP_RE = re.compile(
    r"\b(?:partnership|partners\s+with|deal|partenariat|accord|collaboration)\b"
)

# Importance sub-signal 2 — business magnitude (0-12 / 9 / 6 / 0).
_BILLION_RE = re.compile(r"\b(?:billion|billions|milliard|milliards)\b")
_HUNDREDS_M_RE = re.compile(r"\b[1-9]\d{2,}\s*(?:million|millions)\b")
_MILLION_RE = re.compile(r"\b(?:million|millions)\b")

# Importance sub-signal 3 — major actors (8 frontier lab / 5 big tech / 0).
_FRONTIER_RE = re.compile(
    r"\b(?:openai|anthropic|deepmind|google|meta|microsoft|nvidia|mistral|"
    r"gemini|claude|gpt)\b"
)
_BIGTECH_RE = re.compile(
    r"\b(?:apple|amazon|samsung|huawei|tesla|spacex|intel|amd|qualcomm|oracle|"
    r"ibm|tiktok|netflix)\b"
)

# Relevance (0-22) — distinct tech-vocab hits x 3, capped.
_RELEVANCE_TOKENS: tuple[str, ...] = (
    "ai",
    "ia",
    "artificial intelligence",
    "intelligence artificielle",
    "machine learning",
    "apprentissage automatique",
    "deep learning",
    "llm",
    "gpt",
    "neural",
    "algorithm",
    "algorithme",
    "software",
    "logiciel",
    "hardware",
    "startup",
    "cloud",
    "data",
    "donnees",
    "api",
    "semiconductor",
    "robot",
    "quantum",
    "quantique",
    "cyber",
    "saas",
    "platform",
    "plateforme",
    "automation",
    "automatisation",
    "application",
    "agent",
    "dataset",
    "gpu",
    "datacenter",
    "fintech",
    "blockchain",
    "crypto",
    "model",
    "modele",
    "chatbot",
    "compute",
    "open source",
    "open-source",
)
_RELEVANCE_RE = re.compile(r"\b(?:" + "|".join(_RELEVANCE_TOKENS) + r")\b")

# MENA / Afrique / Maroc (0-16) — distinct hits x 8, capped.
_MENA_TOKENS: tuple[str, ...] = (
    "maroc",
    "morocco",
    "marocain",
    "maghreb",
    "afrique",
    "africa",
    "africain",
    "mena",
    "cedeao",
    "uemoa",
    "casablanca",
    "rabat",
    "marrakech",
    "tunisie",
    "tunis",
    "algerie",
    "algeria",
    "egypte",
    "egypt",
    "dubai",
    "emirats",
    "uae",
    "arabie",
    "saoudite",
    "riyadh",
    "yassir",
    "instadeep",
    "wamda",
    "anghami",
    "careem",
    "jumia",
    "sahel",
    "senegal",
    "abidjan",
    "accra",
    "nairobi",
    "lagos",
)
_MENA_RE = re.compile(r"\b(?:" + "|".join(_MENA_TOKENS) + r")\b")


# ---------------------------------------------------------------------------
# v1.1 importance enrichment — ADDITIVE, used ONLY when rank(importance_model=
# "v1_1"). The default rank() path (importance_model="v1") never touches any of
# this, so v1.0 behaviour is byte-identical. Scope: importance composite only —
# no MENA / threshold / weight change. Reuses the v1.0 event/magnitude scorers.
# ---------------------------------------------------------------------------

# Actors — same caps (8 frontier / 5 enterprise), broader lexicon. Supersets of
# the v1.0 sets, so score_actors_v1_1 >= score_actors for ANY text (monotone).
_FRONTIER_RE_V1_1 = re.compile(
    r"\b(?:openai|anthropic|deepmind|google|meta|microsoft|nvidia|mistral|"
    r"gemini|claude|gpt|xai|grok|deepseek|zhipu|glm|cohere|huggingface|"
    r"hugging\s+face|perplexity|databricks|scale\s+ai|stability\s+ai)\b"
)
_ENTERPRISE_RE_V1_1 = re.compile(
    r"\b(?:apple|amazon|samsung|huawei|tesla|spacex|intel|amd|qualcomm|oracle|"
    r"ibm|tiktok|netflix|salesforce|sap|servicenow|service\s+now|adobe|"
    r"snowflake|workday|shopify|uber|atlassian)\b"
)

# Strategic category (0-12) — TIGHTENED (v1.1 calibration round 2) after the
# corpus run showed the broad lexicon over-firing on consumer/OS/shopping noise
# (Prime Day, Toy Story, Windows/Linux/Android). Generic tokens (standard /
# framework / specification / benchmark / datacenter) are removed; each category
# now carries a strong gate. 12-pt structural tiers are checked before 10-pt
# strategic-move tiers so the returned value is the MAX.

# Strong AI entity — required to license market_structure & frontier_move.
_AI_ENTITY_RE = re.compile(
    r"\b(?:openai|anthropic|claude|chatgpt|google|deepmind|gemini|meta|llama|"
    r"mistral|nvidia|microsoft|copilot|deepseek|cohere|huggingface|hugging\s+face|"
    r"grok|xai)\b"
)
# OS / consumer / entertainment context — BLOCKS infra_standards & frontier_move
# (Microsoft/Google are AI entities but Windows/Android stories are not moves).
_OS_CONSUMER_RE = re.compile(
    r"\b(?:windows|linux|android|ios|macos|mac\s+os|office|euro-?office|"
    r"prime\s+day|toy\s+story|airpods|playstation|xbox|nintendo|smartphone|"
    r"videoprojecteur|ecouteurs|lunettes|ar\s+glasses|projector|radio\s+fm)\b"
)
# Agent / LLM terms that license a bare "protocol" as an infra signal.
_AGENT_LLM_RE = re.compile(r"\b(?:agent|agents|agentic|llm|llms|mcp|model\s+context)\b")

# infra_standards — ONLY very specific signals (no generic standard/framework).
_STRATEGIC_INFRA_SPECIFIC_RE = re.compile(
    r"\b(?:open\s+knowledge\s+format|model\s+context\s+protocol|mcp|agent\s+protocol)\b"
)
_STRATEGIC_PROTOCOL_RE = re.compile(r"\bprotocol(?:e|s)?\b")

# market_structure — keyword; only counts WITH a strong AI entity (gated below).
_STRATEGIC_MARKET_RE = re.compile(
    r"\b(?:market\s+share|part\s+de\s+marche|overtakes?|surpasses?|depasse\w*|"
    r"market\s+leader|leading\s+ai|abonnements?\s+ia)\b"
)
# sovereignty_policy / enterprise_labor — unchanged (not flagged as noisy).
_STRATEGIC_SOVEREIGNTY_RE = re.compile(
    r"\b(?:souverain\w*|sovereignty|national\s+ai|ai\s+act|executive\s+order|"
    r"public\s+funding|european\s+ai)\b"
)
_STRATEGIC_LABOR_RE = re.compile(
    r"\b(?:layoffs?|job\s+cuts|workforce|effectifs|reduce\s+staff|"
    r"enterprise\s+customers|rolls?\s+out\s+to\s+enterprise)\b"
)
# Concrete-move signal that licenses sovereignty_policy (Round-3): deployment /
# integration VERBS only. Excluded as too generic: product/service/api (every
# policy piece mentions a "service") AND the French NOUN "déploiement" (fires on
# infra/debate pieces like "déploiement de data centers"); the active verb forms
# (deploy\w* → deploy/deployer/deployment, generalise, adopt) are sufficient and
# keep the genuine deployments (verified on corpus: #2092/#2231 stay, #2253/#1984 drop).
_STRATEGIC_MOVE_RE = re.compile(
    r"\b(?:deploy\w*|rollout|roll\s+out|generalis\w*|generaliz\w*|"
    r"adopt\w*|integrat\w*|integre\w*|copilot|embed)\b"
)
# frontier_move — clear PRODUCT/access/model action; only WITH a strong AI entity
# and NOT OS/consumer. Round-3 TIGHTENED: bare verification/access/api/feature
# removed (they fired on non-events like a "no traffic drop observed" story);
# integration tokens added so a model integrated into a product is captured.
_STRATEGIC_FRONTIER_ACTION_RE = re.compile(
    r"\b(?:identity\s+verification|age\s+verification|papiers\s+d|"
    r"safety|alignment|enterprise\s+ai|deprecat\w*|rate\s+limit|content\s+policy|"
    r"model\s+(?:update|change|release|launch|access)|"
    r"integrat\w*|integre\w*|copilot|embed)\b"
)


# ---------------------------------------------------------------------------
# Pure sub-score functions (input = NFKD-normalized lower-case text)
# ---------------------------------------------------------------------------


def score_event_type(norm_text: str) -> int:
    if _MAJOR_EVENT_RE.search(norm_text):
        return 15
    if _PARTNERSHIP_RE.search(norm_text):
        return 8
    return 0


def score_magnitude(norm_text: str) -> int:
    if _BILLION_RE.search(norm_text):
        return 12
    if _HUNDREDS_M_RE.search(norm_text):
        return 9
    if _MILLION_RE.search(norm_text):
        return 6
    return 0


def score_actors(norm_text: str) -> int:
    if _FRONTIER_RE.search(norm_text):
        return 8
    if _BIGTECH_RE.search(norm_text):
        return 5
    return 0


def score_importance(norm_text: str) -> tuple[int, dict[str, int]]:
    """Dominant composite (0-35) + its sub-parts (for the breakdown)."""
    event = score_event_type(norm_text)
    magnitude = score_magnitude(norm_text)
    actors = score_actors(norm_text)
    total = min(_CAP_IMPORTANCE, event + magnitude + actors)
    return total, {"event_type": event, "magnitude": magnitude, "actors": actors}


def score_actors_v1_1(norm_text: str) -> int:
    """v1.1 actors (0-8). Broader lexicon; superset of v1 → always >= score_actors."""
    if _FRONTIER_RE_V1_1.search(norm_text):
        return 8
    if _ENTERPRISE_RE_V1_1.search(norm_text):
        return 5
    return 0


def score_strategic_category(norm_text: str) -> tuple[int, str]:
    """Strategic editorial importance (0-12) + matched label — TIGHTENED.

    Each category carries a strong gate so consumer/OS/shopping noise scores 0:
      * infra_standards (12): specific tokens, or a bare "protocol" only with an
        agent/LLM or AI-entity context — never on OS/consumer content;
      * market_structure (12): only WITH a strong AI entity;
      * sovereignty_policy / enterprise_labor (10): unchanged, relevance-gated;
      * frontier_move (10): strong AI entity + clear AI action, never OS/consumer.
    12-pt tiers are checked before 10-pt so the returned value is the MAX."""
    if not _RELEVANCE_RE.search(norm_text):
        return 0, "none"

    os_consumer = bool(_OS_CONSUMER_RE.search(norm_text))
    ai_entity = bool(_AI_ENTITY_RE.search(norm_text))

    # 12-pt structural tiers
    if not os_consumer:
        infra = bool(_STRATEGIC_INFRA_SPECIFIC_RE.search(norm_text)) or (
            bool(_STRATEGIC_PROTOCOL_RE.search(norm_text))
            and (ai_entity or bool(_AGENT_LLM_RE.search(norm_text)))
        )
        if infra:
            return 12, "infra_standards"
    # market_structure: strong AI entity + keyword, but NEVER on OS/consumer/
    # entertainment content (an article can name-drop an AI entity in passing).
    if ai_entity and not os_consumer and _STRATEGIC_MARKET_RE.search(norm_text):
        return 12, "market_structure"

    # 10-pt strategic-move tiers.
    # frontier_move is checked BEFORE sovereignty_policy so a product/integration
    # move (e.g. a model integrated into another product) is labelled correctly,
    # not as policy.
    if ai_entity and not os_consumer and _STRATEGIC_FRONTIER_ACTION_RE.search(norm_text):
        return 10, "frontier_move"
    # sovereignty_policy (Round-3): a souveraineté/policy/regulation SIGNAL is no
    # longer enough — it must ALSO carry a strong AI entity AND a concrete
    # deployment/integration move, and NOT be OS/consumer content (an office-suite
    # sovereignty debate is not an AI move). Bare debates score 0.
    if (
        _STRATEGIC_SOVEREIGNTY_RE.search(norm_text)
        and ai_entity
        and not os_consumer
        and _STRATEGIC_MOVE_RE.search(norm_text)
    ):
        return 10, "sovereignty_policy"
    if _STRATEGIC_LABOR_RE.search(norm_text):
        return 10, "enterprise_labor"
    return 0, "none"


def score_importance_v1_1(norm_text: str) -> tuple[int, dict[str, Any]]:
    """v1.1 composite (0-35): event + max(magnitude, strategic_category) + actors.

    `max(magnitude, strategic)` keeps the 0-12 slot shared: a big-number story
    is unchanged (no Sarvam regression), while a low-magnitude but strategically
    important story is lifted. Monotone vs v1: result >= score_importance(...)."""
    event = score_event_type(norm_text)
    magnitude = score_magnitude(norm_text)
    strategic, strategic_label = score_strategic_category(norm_text)
    actors = score_actors_v1_1(norm_text)
    combine = max(magnitude, strategic)
    total = min(_CAP_IMPORTANCE, event + combine + actors)
    return total, {
        "event_type": event,
        "magnitude": magnitude,
        "strategic_category": strategic,
        "strategic_label": strategic_label,
        "actors": actors,
        "combine": combine,
        "model": "v1_1",
    }


def score_relevance(norm_text: str) -> int:
    distinct = len(set(_RELEVANCE_RE.findall(norm_text)))
    return min(_CAP_RELEVANCE, distinct * 3)


def score_mena(norm_text: str) -> int:
    distinct = len(set(_MENA_RE.findall(norm_text)))
    return min(_CAP_MENA, distinct * 8)


def score_source(source_name: str, tiers: Mapping[str, str]) -> tuple[int, str]:
    """Returns (weight 0-15, tier label) — tier label feeds the breakdown."""
    tier = tiers.get(source_name, "unknown")
    return _TIER_WEIGHTS.get(tier, _UNKNOWN_TIER_WEIGHT), tier


def score_freshness(published_at: datetime | None, fetched_at: datetime, now: datetime) -> int:
    """0-12, linear decay from full (≤6h) to zero (≥48h). Uses published_at,
    falling back to fetched_at. Future-dated articles clamp to full."""
    ref = published_at if published_at is not None else fetched_at
    hours = (now - ref).total_seconds() / 3600.0
    if hours <= _FRESH_FULL_HOURS:
        return _CAP_FRESHNESS
    if hours >= _FRESH_ZERO_HOURS:
        return 0
    frac = (_FRESH_ZERO_HOURS - hours) / (_FRESH_ZERO_HOURS - _FRESH_FULL_HOURS)
    return round(_CAP_FRESHNESS * frac)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RankInput:
    title: str
    content: str
    source_name: str
    published_at: datetime | None
    fetched_at: datetime


@dataclass(frozen=True)
class RankResult:
    score: int
    decision: str  # "selected" | "deferred"
    breakdown: dict[str, Any]


def decide(score: int, threshold: int) -> str:
    """Threshold-only decision. Quota enforcement is the JOB's responsibility
    (a later step), NOT this pure scorer."""
    return "selected" if score >= threshold else "deferred"


def rank(
    item: RankInput,
    *,
    tiers: Mapping[str, str],
    now: datetime,
    threshold: int,
    importance_model: str = "v1",
) -> RankResult:
    """Score one article /100 and return score + decision + structured breakdown.

    Pure: depends only on its arguments. `tiers`, `now` and `threshold` are
    injected (from config at the call site), never read here.

    `importance_model` selects the importance composite: "v1" (default) is the
    production v1.0 behaviour, byte-identical; "v1_1" enables the enriched
    strategic-importance + broader-actors model for OFFLINE comparison only.
    Only the `importance` axis differs — relevance/MENA/source/freshness and the
    threshold are untouched in both modes.
    """
    norm = _normalize(f"{item.title} {item.content}")

    if importance_model == "v1_1":
        importance, importance_detail = score_importance_v1_1(norm)
    else:
        importance, importance_detail = score_importance(norm)
    relevance = score_relevance(norm)
    mena = score_mena(norm)
    source_weight, tier = score_source(item.source_name, tiers)
    freshness = score_freshness(item.published_at, item.fetched_at, now)

    total = importance + relevance + mena + source_weight + freshness
    breakdown: dict[str, Any] = {
        "total": total,
        "importance": importance,
        "relevance": relevance,
        "mena": mena,
        "source": source_weight,
        "freshness": freshness,
        "importance_detail": importance_detail,
        "source_tier": tier,
    }
    return RankResult(score=total, decision=decide(total, threshold), breakdown=breakdown)
