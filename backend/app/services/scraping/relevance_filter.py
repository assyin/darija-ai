from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

AI_KEYWORDS: frozenset[str] = frozenset(
    {
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
    haystack = f"{title} {content[:500]}".lower()
    if not any(kw in haystack for kw in AI_KEYWORDS):
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
