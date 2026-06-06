"""Tests for the multilingual relevance filter.

These pin the new contract introduced with the MENA + Francophonie sources
rollout: the filter must accept FR-language AI coverage from Frenchweb /
Maddyness / Le Devoir, Arabic coverage from Asharq Al-Awsat / Médias24 ar,
and brand-only mentions (Mila, Yassir, InstaDeep) without needing the
literal string "ai" / "intelligence artificielle" to appear.

Each test states what it's defending, so a future change that breaks
the contract is easy to read in the diff.
"""

from __future__ import annotations

import pytest

from app.services.scraping.relevance_filter import (
    MIN_WORD_COUNT,
    is_relevant,
    normalize_url,
    url_hash,
)

# A canned body long enough to clear MIN_WORD_COUNT (80 words). Tests append
# their own topic-bearing prefix to it so we test the topic gate, not length.
_PADDING = " ".join(["lorem", "ipsum", "dolor", "sit", "amet"] * 20)  # 100 words


# -----------------------------------------------------------------------------
# English (regression — must still pass after the v2 expansion)
# -----------------------------------------------------------------------------


def test_english_artificial_intelligence_phrase_passes() -> None:
    """Baseline: the legacy v1 keyword set still matches."""
    ok, reason = is_relevant("Why artificial intelligence matters", _PADDING)
    assert ok is True
    assert reason is None


def test_english_brand_only_passes() -> None:
    """An article naming Claude/OpenAI without the literal "AI" still passes."""
    ok, _ = is_relevant("Claude beats benchmarks", _PADDING)
    assert ok is True


# -----------------------------------------------------------------------------
# French — accent-insensitive matching is the central new contract
# -----------------------------------------------------------------------------


def test_french_intelligence_artificielle_passes() -> None:
    """Canonical FR phrase — the most common signal in Frenchweb / Maddyness."""
    ok, _ = is_relevant("L'intelligence artificielle transforme la pub", _PADDING)
    assert ok is True


def test_french_capitalised_with_accents_passes() -> None:
    """A title with capitals + accents must canonicalise to the same key."""
    # "INTÉLLIGENCE ARTIFICIELLE" → lowered + NFKD-stripped =
    # "intelligence artificielle"
    ok, _ = is_relevant("INTÉLLIGENCE ARTIFICIELLE AU SERVICE DE LA SANTÉ", _PADDING)
    assert ok is True


def test_french_ia_generative_passes() -> None:
    """Accent-bearing phrase IA générative becomes 'ia generative'."""
    ok, _ = is_relevant("L'IA générative bouleverse le marketing", _PADDING)
    assert ok is True


def test_french_modele_de_langage_passes() -> None:
    """`modèle de langage` (FR for LLM) — accent on è must not block."""
    ok, _ = is_relevant("Le nouveau modèle de langage de Mistral", _PADDING)
    assert ok is True


def test_french_standalone_ia_token_passes_with_padding() -> None:
    """Standalone "IA" inside the title — must be padded to avoid 'Italie' etc."""
    # Real Maddyness headline pattern: "L' IA en 2026" → contains " ia "
    ok, _ = is_relevant("Sommet IA Paris : ce qu'il faut retenir", _PADDING)
    assert ok is True


def test_french_italie_does_not_match_ia_token() -> None:
    """Defensive: "Italie" must NOT match the padded " ia " token."""
    # No other AI keyword present → must reject.
    ok, reason = is_relevant("L'Italie signe un accord économique", _PADDING)
    assert ok is False
    assert reason == "no_ai_keywords"


# -----------------------------------------------------------------------------
# Arabic — Asharq Al-Awsat / Medias24 ar coverage
# -----------------------------------------------------------------------------


def test_arabic_ai_phrase_passes() -> None:
    """`ذكاء اصطناعي` in the title — most common MSA signal."""
    # Pad with neutral Arabic so we clear MIN_WORD_COUNT and don't fall back
    # on counting Latin lorem-ipsum words.
    arabic_body = "مرحبا " * 90
    ok, _ = is_relevant("ذكاء اصطناعي يغير الصناعة", arabic_body)
    assert ok is True


def test_arabic_with_definite_article_passes() -> None:
    """`الذكاء الاصطناعي` (with definite article) — same concept, different morphology."""
    arabic_body = "نص طويل " * 50
    ok, _ = is_relevant("الذكاء الاصطناعي والمستقبل", arabic_body)
    assert ok is True


# -----------------------------------------------------------------------------
# Brand + ecosystem signals — MENA, Francophonie, Quebec
# -----------------------------------------------------------------------------


def test_mila_montreal_passes() -> None:
    """Quebec AI institute — every mention is AI-relevant for our scope."""
    ok, _ = is_relevant("Mila lance un nouveau programme de recherche", _PADDING)
    assert ok is True


def test_yoshua_bengio_passes() -> None:
    """Founder-of-Mila signal."""
    ok, _ = is_relevant("Yoshua Bengio signe une tribune sur la sûreté", _PADDING)
    assert ok is True


def test_french_tech_signal_passes() -> None:
    """`French Tech` ecosystem mention — AI-adjacent enough for our editorial scope."""
    ok, _ = is_relevant("La French Tech lève 1 milliard cette semaine", _PADDING)
    assert ok is True


def test_instadeep_passes() -> None:
    """Tunisian AI unicorn (BioNTech acquired)."""
    ok, _ = is_relevant("InstaDeep ouvre un bureau au Caire", _PADDING)
    assert ok is True


def test_yassir_passes() -> None:
    """Maghreb super-app driven by ML for routing/dispatch."""
    ok, _ = is_relevant("Yassir lève 100 millions pour son IA logistique", _PADDING)
    assert ok is True


# -----------------------------------------------------------------------------
# Threshold + rejection paths (regression — unchanged behaviour)
# -----------------------------------------------------------------------------


def test_word_count_threshold_still_rejects_short_articles() -> None:
    """A keyword hit but a too-short body — must still reject."""
    ok, reason = is_relevant("Intelligence artificielle révolutionne tout", "court.")
    assert ok is False
    assert reason == "too_short"


def test_word_count_boundary_is_inclusive_above() -> None:
    """Exactly MIN_WORD_COUNT + 1 words → accepted (sanity check on the gate)."""
    body = " ".join(["mot"] * (MIN_WORD_COUNT + 1))
    ok, _ = is_relevant("IA générative en entreprise", body)
    assert ok is True


def test_completely_unrelated_article_rejected() -> None:
    """Weather report → no AI keyword, no brand → reject cleanly."""
    ok, reason = is_relevant("Météo : pluie attendue à Casablanca", _PADDING)
    assert ok is False
    assert reason == "no_ai_keywords"


def test_keyword_in_body_alone_still_passes() -> None:
    """Topic might surface only in the body (first 500 chars are scanned)."""
    body = "Le secteur traverse une mutation. " + "lorem ipsum dolor sit amet " * 5
    body += " La nouvelle vague d'IA générative pousse les acteurs à investir."
    body += " " + _PADDING  # ensure length
    ok, _ = is_relevant("Le secteur traverse une mutation", body)
    assert ok is True


# -----------------------------------------------------------------------------
# URL normalisation (regression — pinned by existing pipeline behaviour)
# -----------------------------------------------------------------------------


def test_normalize_url_strips_utm() -> None:
    out = normalize_url("https://medias24.com/article?utm_source=twitter&id=42")
    assert out == "https://medias24.com/article?id=42"


def test_normalize_url_strips_trailing_slash() -> None:
    a = normalize_url("https://wamda.com/article/")
    b = normalize_url("https://wamda.com/article")
    assert a == b


def test_url_hash_stable_for_equivalent_urls() -> None:
    """Two URLs differing only in tracking params hash to the same key."""
    a = url_hash("https://maddyness.com/x?utm_campaign=foo")
    b = url_hash("https://maddyness.com/x")
    assert a == b


# Parametric sanity matrix — quick regression sweep on canonical signals.
@pytest.mark.parametrize(
    "title",
    [
        "Anthropic dévoile son nouveau modèle",
        "OpenAI annonce GPT-5",
        "La France investit dans la French Tech",
        "Bpifrance soutient une startup IA",
        "Bengio: l'IA générative arrive",
        "Mila publie un nouveau benchmark",
        "حوار حول الذكاء الاصطناعي مع خبراء",
    ],
)
def test_canonical_topic_sweep(title: str) -> None:
    ok, _ = is_relevant(title, _PADDING)
    assert ok is True, f"Expected '{title}' to be relevant"
