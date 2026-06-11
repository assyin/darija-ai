"""Decide whether a raw article is tech-relevant enough to enter the pipeline.

Why this gate exists: TitritAI ingests from sources that cover MUCH more than
tech (Médias24, Le Devoir, Frenchweb, La Presse, Swiss/Quebec general news) —
relying on the source alone pushes every politics / weather / sports story into
Claude. This filter is the FIRST cheap gate, before we spend a single Localizer
call (~$0.04 of mostly-input tokens). Articles rejected here are never stored
and never reach Claude.

Editorial scope is **tech-large** (validated 2026-06-11 against the published
corpus): AI, but also startups, fintech, hardware, gaming, consumer tech,
infrastructure and tech-business. Strictly-AI-only would filter content the
newsroom actually publishes (Uber/Careem, GoPro, OLED TVs, EVs…).

Matching rules (V8, validated by production replay — see
``tests/.../test_relevance_filter.py::test_offline_corpus_reproduces_measured``):

  block (return ``(False, reason)``) if:
      NOT( tech keyword in TITLE  OR  >= 2 tech hits in title+body )   # "no_tech_signal"
    OR
      len(content) < 400 chars                                        # "too_short"

The keyword check runs FIRST so off-topic articles return ``no_tech_signal``
(not eligible for HTML enrichment), while a genuinely-tech-but-short excerpt
returns ``too_short`` and the ingestion path may enrich it then re-test.

Critical correctness note — WORD BOUNDARIES:
  The previous version matched keywords as bare substrings. The 2-letter token
  "ai" is a substring of common French words (m**ai**s, m**ai**son, fr**ai**s,
  tr**ai**l, j**ai**, **ai**r, fran**çai**s→francais) so 96% of the corpus
  "matched" and the gate was a no-op for French — every off-topic article
  reached Claude and was rejected there at full input cost. All short Latin
  tokens are now word-boundary anchored. See the regression test
  ``test_ai_substring_in_mais_does_not_match``.

Three keyword families:
  - Latin (FR + EN): matched against an NFKD-normalized, diacritic-stripped,
    lower-cased haystack so "Intelligence Artificielle" and "intelligence
    artificielle" hit the same canonical entry. Single-word tokens are
    word-boundary anchored; multi-word / hyphenated phrases are specific
    enough to match literally.
  - Arabic: matched as a literal substring against the raw lower-cased
    haystack (Arabic has no "ai"-style short-token collision, and lowercase
    is a no-op for Arabic letters).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _strip_accents(s: str) -> str:
    """Lower-case + NFKD-strip combining diacritics.

    "Génération" → "generation", "État" → "etat", "français" → "francais".
    Arabic letters survive unchanged (their tashkīl marks are stripped too,
    which is what we want — news prose rarely carries tashkīl).
    """
    decomposed = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Latin tech lexicon (tech-large scope). Stored in accent-stripped lower form
# so the lookup against _strip_accents(haystack) is symmetric.
#
# _SHORT_TOKENS  — single words that are SHORT or ambiguous; word-boundary
#                  anchored so "ai" never matches "mais". Includes the legacy
#                  AI/brand tokens that are real words elsewhere.
# _PHRASE_TOKENS — multi-word, hyphenated, or otherwise specific patterns;
#                  matched literally (their length/structure prevents the
#                  substring collisions that plague 2-3 letter tokens).
# ---------------------------------------------------------------------------

# Single-word tokens — emitted inside a single \b(?:...)\b group.
_WORD_TOKENS: tuple[str, ...] = (
    # AI / ML core
    "ai",
    "ia",
    "llm",
    "gpt",
    "chatgpt",
    "openai",
    "anthropic",
    "claude",
    "gemini",
    "copilot",
    "chatbot",
    "neural",
    "transformer",
    "inference",
    "pretrain",
    "embedding",
    "embeddings",
    "dataset",
    "benchmark",
    "pytorch",
    "tensorflow",
    "generative",
    "generatif",
    "deepfake",
    "prompt",
    "agentic",
    "algorithm",
    "algorithme",
    "nlp",
    "tln",
    "rag",
    "mistral",
    "llama",
    "midjourney",
    "dalle",
    # Compute / dev / infra
    "software",
    "logiciel",
    "hardware",
    "startup",
    "blockchain",
    "crypto",
    "bitcoin",
    "web3",
    "semiconductor",
    "nvidia",
    "smartphone",
    "iphone",
    "android",
    "cyber",
    "cybersecurite",
    "quantum",
    "informatique",
    "metaverse",
    "metavers",
    "fintech",
    "developer",
    "developpeur",
    "developpement",
    "programming",
    "programmation",
    "kubernetes",
    "docker",
    "devops",
    "robot",
    "robotique",
    "datacenter",
    "processeur",
    "microchip",
    "chipset",
    "gpu",
    "cpu",
    "tpu",
    "api",
    "amd",
    "ibm",
    "intel",
    # Consumer tech / hardware / gaming
    "autonome",
    "autonomous",
    "driverless",
    "oled",
    "esport",
    "gaming",
    "console",
    "ecouteurs",
    "earbuds",
    "headphone",
    "wearable",
    "streaming",
    # Tech brands (low off-topic collision)
    "google",
    "microsoft",
    "apple",
    "meta",
    "amazon",
    "tesla",
    "spacex",
    "samsung",
    "huawei",
    "qualcomm",
    "uber",
    "tiktok",
    "spotify",
    "netflix",
    "oracle",
    # MENA / Francophonie ecosystem (legacy set — preserved)
    "instadeep",
    "yassir",
    "tabby",
    "tamara",
    "anghami",
    "careem",
    "chari",
    "onecart",
    "mila",
    "ivado",
    "bpifrance",
)

# Multi-word / hyphenated / pattern tokens — matched literally (no \b group).
_PHRASE_TOKENS: tuple[str, ...] = (
    "artificial intelligence",
    "intelligence artificielle",
    "machine learning",
    "deep learning",
    "language model",
    "modele de langage",
    "reseau de neurones",
    "vision par ordinateur",
    "traitement du langage naturel",
    "fine-tun",
    "fine tuning",
    "pre-entra",
    "hugging face",
    "huggingface",
    "stable diffusion",
    "diffusion model",
    "dall-e",
    "start-up",
    "open-source",
    "open source",
    "data center",
    "realite virtuelle",
    "vehicule electrique",
    "voiture autonome",
    "semi-conducteur",
    "self-driving",
    "mini-led",
    "e-sport",
    "jeu video",
    "jeux video",
    "ia generative",
    "ia agentique",
    "ia conversationnelle",
    "generative ai",
    "agent conversationnel",
    "yoshua bengio",
    "vector institute",
    "scale ai",
    "element ai",
    "french tech",
    "station f",
    "smart africa",
    "africa tech",
    "ai act",
    "loi sur l ia",
    "digital morocco",
    "maroc digital",
)

# Funding / venture signals — strong tech-news markers, matched as regex.
_PATTERN_TOKENS: tuple[str, ...] = (
    r"raises? \$",  # "raises $1.5 million"
    r"leve [0-9]",  # "lève 400 millions" (accent-stripped)
    r"levee de fonds",
    r"venture",
)


def _build_tech_regex() -> re.Pattern[str]:
    # Longest-first so a token never shadows a longer one sharing its prefix.
    words = sorted(set(_WORD_TOKENS), key=len, reverse=True)
    phrases = sorted(set(_PHRASE_TOKENS), key=len, reverse=True)
    word_group = r"\b(?:" + "|".join(words) + r")\b"
    phrase_group = "|".join(re.escape(p) for p in phrases)
    pattern_group = "|".join(_PATTERN_TOKENS)
    combined = f"(?:{word_group})|(?:{phrase_group})|(?:{pattern_group})"
    return re.compile(combined, re.IGNORECASE)


_TECH_RE: re.Pattern[str] = _build_tech_regex()


# ---------------------------------------------------------------------------
# Arabic keywords — matched as substrings against the raw lower-cased haystack.
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
        "تقني",  # technical / technology (covers تقني + تقنية)
        "تكنولوجيا",
        "حاسوب",
        "برمجة",
    }
)

# V8 thresholds (validated 2026-06-11).
MIN_CONTENT_CHARS = 400  # below this, an article is a stub — reject (enrichable).
MIN_BODY_HITS = 2  # tech hits required in title+body when the title alone is not tech.

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAM_NAMES = frozenset({"ref", "fbclid", "gclid", "mc_cid", "mc_eid"})


def _arabic_hits(raw_lower: str) -> int:
    # Count occurrences (not distinct keywords) so an Arabic body that repeats
    # one AI phrase contributes to the density gate like the Latin findall path.
    return sum(raw_lower.count(kw) for kw in _AI_KEYWORDS_ARABIC)


def is_relevant(title: str, content: str) -> tuple[bool, str | None]:
    """Return (passes, rejection_reason) for a fetched article.

    First filter on the ingestion path — runs before any AI call and before
    the article is stored. The keyword gate is evaluated first so off-topic
    articles return ``"no_tech_signal"`` (not enrichment-eligible); a
    genuinely tech-but-short body returns ``"too_short"`` and the ingestion
    path may enrich + re-test it.
    """
    title_canon = _strip_accents(title)
    full_canon = _strip_accents(f"{title} {content}")
    raw_lower = f"{title} {content}".lower()

    title_tech = _TECH_RE.search(title_canon) is not None or any(
        kw in title.lower() for kw in _AI_KEYWORDS_ARABIC
    )
    hits = len(_TECH_RE.findall(full_canon)) + _arabic_hits(raw_lower)

    if not (title_tech or hits >= MIN_BODY_HITS):
        return False, "no_tech_signal"

    if len(content) < MIN_CONTENT_CHARS:
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
