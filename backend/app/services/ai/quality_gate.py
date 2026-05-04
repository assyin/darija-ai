from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

if TYPE_CHECKING:
    from app.services.ai.localizer import LocalizedArticle

# Make langdetect deterministic across runs.
DetectorFactory.seed = 0

TAKEAWAY_HEADER = "## شنو كيعني هاد الشي ليك؟"

PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[TODO\]", re.IGNORECASE),
    re.compile(r"\blorem ipsum\b", re.IGNORECASE),
    re.compile(r"<placeholder>", re.IGNORECASE),
    re.compile(r"\bPLACEHOLDER\b", re.IGNORECASE),
)

# Allowlisted Latin tokens that may appear in body text without triggering the
# "raw English residue" check. Match as whole tokens, case-sensitive where it matters.
ALLOWLISTED_LATIN: frozenset[str] = frozenset(
    {
        # Brands / products
        "OpenAI", "ChatGPT", "Anthropic", "Claude", "Google", "Meta", "Microsoft",
        "GitHub", "Hugging", "Face", "Mistral", "NVIDIA", "AMD", "SoftBank",
        "Pinecone", "Weaviate", "LangChain", "LlamaIndex", "Llama", "Gemini",
        "Bard", "Apple", "Amazon", "AWS", "Azure", "DeepMind", "Stability",
        "Midjourney", "Replicate", "Cohere", "Databricks", "Snowflake",
        # Acronyms / short tech terms
        "AI", "LLM", "LLMs", "GPU", "GPUs", "TPU", "API", "APIs", "SDK", "CLI",
        "CEO", "CTO", "CFO", "COO", "VP", "R", "D", "IPO", "AGI", "ASI",
        "RAG", "MoE", "RLHF", "GAN", "GANs", "NLP", "MLOps", "DevOps", "CV",
        "ML", "DL", "OCR", "ASR", "TTS", "NLU", "NLG", "VLM", "VLMs",
        # Dev concepts that appear bare often
        "Embedding", "Embeddings", "Token", "Tokens", "Tokenization",
        "Inference", "Training", "Fine-tuning", "Prompt", "Prompts",
        "Transformer", "Transformers", "Diffusion", "Quantization",
        "Distillation", "Alignment", "Hallucination", "Reasoning",
        "Multimodal", "Benchmark", "Benchmarks", "Compute",
        # Roles often left in Latin
        "Developer", "Developers", "Startup", "Series",
        # Versioned model names — letters part only; numbers aren't matched as words
        "GPT", "Sonnet", "Opus", "Haiku", "Cursor", "Goose",
        "Cowork", "NousCoder", "Nous", "Research",
    }
)

# A "Latin word" for the residue check: 2+ letters (no digits/hyphens). Numbers and
# version strings like "GPT-5" or "100" don't trigger this.
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
_BDI_BLOCK = re.compile(r"<bdi>.*?</bdi>", re.DOTALL)
_H2_LINE = re.compile(r"(?m)^##\s")
_LIST_ITEM = re.compile(r"(?m)^\s*(?:[-*]|\d+\.)\s")
_VALID_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

CONSECUTIVE_LATIN_THRESHOLD = 5
RECOMMENDED_MIN_WORDS = 400
RECOMMENDED_MAX_WORDS = 1200
HARD_MIN_WORDS = 300
HARD_MAX_WORDS = 1500
MIN_H2_COUNT = 2
LANG_CONFIDENCE_THRESHOLD = 0.85


@dataclass(frozen=True)
class QualityCheckResult:
    passed: bool
    failures: list[str]
    warnings: list[str]
    word_count: int
    detected_language: str


def _detect_language(text: str) -> tuple[str, float]:
    sample = text.strip()
    if not sample:
        return "unknown", 0.0
    try:
        results = detect_langs(sample)
    except LangDetectException:
        return "unknown", 0.0
    if not results:
        return "unknown", 0.0
    top = results[0]
    return top.lang, float(top.prob)


def _strip_bdi_blocks(text: str) -> str:
    return _BDI_BLOCK.sub(" ", text)


def _has_english_residue(content: str) -> bool:
    """True if content has 5+ consecutive non-allowlisted Latin words."""
    stripped = _strip_bdi_blocks(content)
    streak = 0
    for match in _LATIN_WORD.finditer(stripped):
        token = match.group()
        if token in ALLOWLISTED_LATIN:
            streak = 0
            continue
        streak += 1
        if streak >= CONSECUTIVE_LATIN_THRESHOLD:
            return True
    return False


class QualityGate:
    """Validates a LocalizedArticle. Returns a QualityCheckResult."""

    def check(self, article: "LocalizedArticle") -> QualityCheckResult:
        failures: list[str] = []
        warnings: list[str] = []

        content = article.content_darija
        word_count = article.word_count

        # Hard 1: language
        lang, confidence = _detect_language(content)
        if lang != "ar" or confidence < LANG_CONFIDENCE_THRESHOLD:
            failures.append("language_not_arabic")

        # Hard 2: word count
        if word_count < HARD_MIN_WORDS:
            failures.append("too_short")
        elif word_count > HARD_MAX_WORDS:
            failures.append("too_long")

        # Hard 3: structure
        if len(_H2_LINE.findall(content)) < MIN_H2_COUNT:
            failures.append("missing_h2_sections")
        if not _LIST_ITEM.search(content):
            failures.append("missing_list")
        if TAKEAWAY_HEADER not in content:
            failures.append("missing_takeaway")

        # Hard 4: placeholders
        for pat in PLACEHOLDER_PATTERNS:
            if pat.search(content):
                failures.append("placeholder_text")
                break

        # Hard 5: English residue heuristic
        if _has_english_residue(content):
            failures.append("english_residue")

        # Soft warnings
        if len(article.title_darija) > 70:
            warnings.append("title_too_long")
        if len(article.excerpt_darija) > 160:
            warnings.append("excerpt_too_long")
        if not _VALID_SLUG.match(article.slug):
            warnings.append("slug_invalid")
        if not (1 <= len(article.categories) <= 3):
            warnings.append("categories_invalid_count")
        if not (RECOMMENDED_MIN_WORDS <= word_count <= RECOMMENDED_MAX_WORDS):
            warnings.append("word_count_suboptimal")

        return QualityCheckResult(
            passed=not failures,
            failures=failures,
            warnings=warnings,
            word_count=word_count,
            detected_language=lang,
        )
