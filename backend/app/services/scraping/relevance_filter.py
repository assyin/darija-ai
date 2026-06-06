"""Decide whether a raw article is AI-relevant enough to enter the pipeline.

Why the keyword soup: TitritAI ingests from sources that cover MUCH more than
AI (Médias24, Le Devoir, Frenchweb) — relying on the source alone would push
every politics or weather story into Claude. The relevance filter is the first
cheap gate before we spend $0.002+ on a Localizer call.

Three keyword families:

  - **Accent-insensitive (FR + EN)**: matched against an NFKD-normalized,
    diacritic-stripped lower-cased haystack so "Intelligence Artificielle",
    "intelligence artificielle" and "INTÉLLIGENCE ARTIFICIELLE" all match
    the same canonical entry "intelligence artificielle".
  - **Arabic**: matched against the original (lower-cased) haystack — Arabic
    has its own diacritics (tashkīl) but they're rare in news prose, and
    lowercase is a no-op for Arabic letters, so a literal substring match
    is reliable.
  - **Brand/program names**: companies and initiatives whose mere mention
    almost always implies an AI angle in TitritAI's editorial scope
    (Mila, Yoshua Bengio, French Tech, Bpifrance, InstaDeep, Yassir AI lab,
    Tabby, Anghami, etc.). These ride in the accent-insensitive set.
"""

from __future__ import annotations

import hashlib
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _strip_accents(s: str) -> str:
    """Lower-case + NFKD-strip combining diacritics.

    "Génération" → "generation", "État" → "etat", "Sénégal" → "senegal".
    Arabic letters survive unchanged because their combining marks
    (tashkīl) are stripped too — which is what we want, news rarely
    uses tashkīl and removing it canonicalises any stray marks.
    """
    decomposed = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Accent-insensitive keywords — matched against _strip_accents(haystack).
# Always store the post-strip form (no accents) so the lookup is symmetric.
# ---------------------------------------------------------------------------
_AI_KEYWORDS_LATIN: frozenset[str] = frozenset(
    {
        # --- English (existing v1 set, preserved) ---
        "ai",
        "a.i.",
        "artificial intelligence",
        "llm",
        "language model",
        "machine learning",
        "ml ",
        "deep learning",
        "neural network",
        "neural net",
        "openai",
        "anthropic",
        "claude",
        "gpt",
        "chatgpt",
        "gemini",
        "mistral",
        "llama",
        "huggingface",
        "hugging face",
        "transformer",
        "diffusion model",
        "agent",
        "agentic",
        "rag ",
        "fine-tuning",
        "fine tuning",
        "embedding",
        "stable diffusion",
        "midjourney",
        "dall-e",
        "dalle",
        # --- French (accent-stripped canonical forms) ---
        "intelligence artificielle",  # IA in nearly every FR newsroom
        " ia ",  # standalone token, padded to avoid matching e.g. "italie"
        " ia.",
        " ia,",
        "ia generative",  # "IA générative"
        "ia agentique",  # "IA agentique"
        "ia conversationnelle",
        "apprentissage automatique",
        "apprentissage profond",
        "modele de langage",  # "modèle de langage"
        "grands modeles de langage",  # "grands modèles de langage"
        "reseau de neurones",  # "réseau de neurones"
        "agent conversationnel",
        "agent intelligent",
        "vision par ordinateur",
        "traitement du langage naturel",
        "tln",  # TLN abbreviation
        "generative ai",  # bilingual coverage
        # --- Brands + ecosystem signals (FR / EN / MENA) ---
        # MENA/Morocco AI-adjacent companies & initiatives.
        "instadeep",  # Tunisian AI unicorn (BioNTech acquisition).
        "yassir",  # Algerian/Maghreb super-app, AI-driven logistics.
        "tabby",  # KSA fintech, ML-based credit scoring.
        "tamara",  # KSA fintech, same.
        "anghami",  # MENA Spotify, ML recommendations.
        "careem",  # MENA Uber, AI dispatch.
        "chari",  # Moroccan B2B marketplace.
        "onecart",  # Moroccan logistics.
        "digital morocco 2030",
        "maroc digital 2030",
        # Francophonie ecosystem.
        "mila",  # Montreal Institute for Learning Algorithms.
        "yoshua bengio",  # Mila founder, AI godfather.
        "vector institute",  # Toronto AI hub (Hinton-era).
        "ivado",  # Quebec AI institute, IVADO.
        "scale ai canada",  # Canadian AI ecosystem org.
        "element ai",  # Quebec AI scale-up (ServiceNow acq).
        "french tech",  # FR ecosystem brand.
        "la french tech",
        "bpifrance",  # State-owned French Tech funder.
        "station f",  # FR startup campus.
        # "hugging face" and "mistral" already listed in the EN section above.
        # Pan-African + EU policy signals.
        "smart africa",  # Pan-African digital initiative.
        "africa tech",
        "ai act",  # EU AI Act, often cited as "AI Act" in FR press.
        "loi sur l'ia",  # FR rendering of the AI Act.
        "loi sur l ia",  # accent-stripped of the apostrophe-less form.
    }
)


# ---------------------------------------------------------------------------
# Arabic keywords — matched against the raw lowercased haystack.
# ---------------------------------------------------------------------------
_AI_KEYWORDS_ARABIC: frozenset[str] = frozenset(
    {
        "ذكاء اصطناعي",
        "الذكاء الاصطناعي",
        "الذكاء الإصطناعي",
        "نماذج لغوية",
        "نموذج لغوي",
        "تعلم آلي",
        "تعلم الآلة",
        "التعلم العميق",
        "الشبكات العصبية",
        "ذكاء اصطناعي توليدي",
        "الذكاء الاصطناعي التوليدي",
        "وكلاء الذكاء",
        "روبوت محادثة",
    }
)


# Modern RSS feeds (TechCrunch, HuggingFace blog, etc.) only carry a short
# excerpt in the feed body — the full article lives on the source website.
# 80 words is a balance between letting these excerpts through and keeping a
# minimum quality threshold to limit hallucination risk in the localizer.
# A future enrichment step (fetch + readability on the URL) can raise this
# back up once we extract full HTML.
MIN_WORD_COUNT = 80

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAM_NAMES = frozenset({"ref", "fbclid", "gclid", "mc_cid", "mc_eid"})


def is_relevant(title: str, content: str) -> tuple[bool, str | None]:
    """Return (passes, rejection_reason) for a fetched article.

    First filter we apply on the ingestion path — runs before any AI call.
    Caller passes the raw title + body text (RSS excerpt or enriched HTML);
    we look at the title plus the first 500 chars of body, which is where
    the topic signal almost always lives.
    """
    raw = f"{title} {content[:500]}"
    raw_lower = raw.lower()
    canonical = _strip_accents(raw)  # lowercased + accent-stripped

    matched = any(kw in canonical for kw in _AI_KEYWORDS_LATIN) or any(
        kw in raw_lower for kw in _AI_KEYWORDS_ARABIC
    )
    if not matched:
        return False, "no_ai_keywords"

    word_count = len(content.split())
    if word_count < MIN_WORD_COUNT:
        return False, "too_short"

    return True, None


def _is_tracking_param(name: str) -> bool:
    lname = name.lower()
    if lname in _TRACKING_PARAM_NAMES:
        return True
    return any(lname.startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES)


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") if parts.path != "/" else ""

    kept_params = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(k)
    ]
    query = urlencode(kept_params, doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()
