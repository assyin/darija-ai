"""Tests for the tech-relevance pre-filter (V8).

Three concerns are pinned here:

1. **Regression** — the bare-substring "ai" bug. Before V8, "ai" matched as a
   substring of common French words (mais, maison, français…), making the gate
   a no-op for French: 96% of the corpus passed and every off-topic article
   reached Claude. The boundary-anchored matcher must NOT match those.
2. **Contract** — the V8 rule: block unless (tech kw in title) OR (>= 2 tech
   hits in title+body); plus a 400-char floor (enrichment-eligible).
3. **Production parity** — an offline replay over the real labeled corpus
   (141 JUNK rejected by the Localizer, 219 GOOD that produced articles)
   reproduces the measured block rates, so the code matches the simulation.

Each test states what it defends so a contract change is obvious in the diff.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from app.services.scraping.relevance_filter import (
    MIN_BODY_HITS,
    MIN_CONTENT_CHARS,
    is_relevant,
    normalize_url,
    url_hash,
)

# Neutral filler with NO tech tokens and NO "ai" substring — long enough to
# clear the 400-char floor so tests exercise the topic gate, not the length gate.
_PAD = "lorem ipsum dolor sit amet consectetur " * 15  # ~585 chars


# ---------------------------------------------------------------------------
# 1. REGRESSION — the "ai" substring bug must stay dead
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Le maire de Montréal présente son budget",  # "maire" contains 'ai'
        "Jamais deux sans trois pour les Canadiens",  # "jamais"
        "La maison de la culture rouvre ses portes",  # "maison"
        "Le parti français débat de la nouvelle loi",  # "français"
        "Le travail parlementaire reprend en septembre",  # "travail"
        "Pour quelle raison le conseil a-t-il voté ainsi",  # "raison"
        "Un air de fête flotte sur la vieille ville",  # "air"
    ],
)
def test_ai_substring_in_common_french_words_does_not_match(title: str) -> None:
    """The 2-letter token 'ai' must be word-bounded — never match mais/français/etc.

    This is THE regression guard for the no-op bug that let every off-topic
    French article reach Claude at full input cost.
    """
    ok, reason = is_relevant(title, "Un article de politique locale. " + _PAD)
    assert ok is False, f"{title!r} wrongly classified tech"
    assert reason == "no_tech_signal"


# ---------------------------------------------------------------------------
# 2. CONTRACT — the V8 rule
# ---------------------------------------------------------------------------


def test_tech_keyword_in_title_passes_regardless_of_density() -> None:
    """A tech keyword in the TITLE passes even with a thin body."""
    ok, reason = is_relevant("OpenAI dévoile GPT-5", "Une annonce courte. " + _PAD)
    assert ok is True
    assert reason is None


def test_single_body_keyword_is_insufficient() -> None:
    """Non-tech title + ONE body hit → rejected (density < 2). Deliberate V8 hardening."""
    body = "Le marché évolue. La blockchain est citée une fois. " + _PAD
    ok, reason = is_relevant("Le secteur traverse une mutation", body)
    assert ok is False
    assert reason == "no_tech_signal"


def test_two_body_keywords_pass() -> None:
    """Non-tech title + TWO tech hits in the body → passes."""
    body = "La startup mise sur la blockchain pour grandir. " + _PAD
    ok, reason = is_relevant("Une jeune pousse en pleine croissance", body)
    assert ok is True
    assert reason is None


def test_density_threshold_constant_is_two() -> None:
    """Guard the documented threshold so a silent change is caught."""
    assert MIN_BODY_HITS == 2


def test_short_tech_article_is_too_short_not_offtopic() -> None:
    """A tech-but-short body returns 'too_short' so ingestion can enrich + re-test."""
    ok, reason = is_relevant("Startup IA marocaine en vue", "Brève.")
    assert ok is False
    assert reason == "too_short"


def test_offtopic_short_article_is_no_tech_signal_not_too_short() -> None:
    """Off-topic short body returns 'no_tech_signal' (NOT enrichment-eligible).

    Keyword gate runs before the length gate: we don't waste an enrichment
    fetch on an article that has no tech signal in the first place.
    """
    ok, reason = is_relevant("Le maire vote le budget municipal", "Brève.")
    assert ok is False
    assert reason == "no_tech_signal"


def test_content_floor_constant_is_400() -> None:
    assert MIN_CONTENT_CHARS == 400


def test_content_just_above_floor_with_tech_title_passes() -> None:
    body = "x" * (MIN_CONTENT_CHARS + 1)
    ok, _ = is_relevant("Nouveau smartphone Android", body)
    assert ok is True


# ---------------------------------------------------------------------------
# 2b. CONTRACT — real off-topic categories that flooded the Localizer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Élections cantonales : le parti socialiste vaudois en tête",
        "Un film suisse primé au festival de cinéma de Locarno",
        "La LNH dévoile le calendrier de la prochaine saison de hockey",
        "Royal Air Maroc inaugure un vol direct Casablanca-Los Angeles",
        "Le pape nomme un nouvel évêque pour le diocèse de Madrid",
        "Marhaba 2026 : ce qui change à la douane pour les MRE",
    ],
)
def test_real_offtopic_titles_rejected(title: str) -> None:
    ok, reason = is_relevant(title, "Un article généraliste sans angle tech. " + _PAD)
    assert ok is False
    assert reason == "no_tech_signal"


def test_italie_does_not_match_ia_token() -> None:
    """Boundary guard preserved from v1: 'Italie' must not trigger the 'ia' token."""
    ok, reason = is_relevant("L'Italie signe un accord économique", _PAD)
    assert ok is False
    assert reason == "no_tech_signal"


# ---------------------------------------------------------------------------
# 2c. CONTRACT — genuine tech (incl. tech-large additions) must pass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Anthropic dévoile son nouveau modèle Claude",
        "OpenAI annonce GPT-5",
        "L'intelligence artificielle transforme la publicité",
        "L'IA générative bouleverse le marketing",
        "La French Tech lève 1 milliard cette semaine",
        "Mila publie un nouveau benchmark",
        "Yassir lève 100 millions pour son IA logistique",
        "TCL lance une TV OLED 240 Hz pour les joueurs",  # tech-large: display/gaming
        "Essai de la nouvelle voiture électrique autonome",  # tech-large: EV/autonomous
        "حوار حول الذكاء الاصطناعي مع خبراء",  # Arabic
    ],
)
def test_genuine_tech_titles_pass(title: str) -> None:
    ok, _ = is_relevant(title, _PAD)
    assert ok is True, f"Expected {title!r} to pass"


def test_arabic_body_signal_passes() -> None:
    body = "نص عربي طويل حول الذكاء الاصطناعي " * 20
    ok, _ = is_relevant("تطور تقني جديد", body)
    assert ok is True


# ---------------------------------------------------------------------------
# 3. PRODUCTION PARITY — offline replay on the real labeled corpus
# ---------------------------------------------------------------------------

_FIXTURE = Path(__file__).parents[3] / "fixtures" / "prefilter_labeled_corpus.json.gz"


def _load_corpus() -> list[dict[str, str]]:
    with gzip.open(_FIXTURE, "rt", encoding="utf-8") as fh:
        data: list[dict[str, str]] = json.load(fh)
    return data


def test_offline_corpus_reproduces_measured_block_rates() -> None:
    """Replay the V8 filter over the real labeled corpus and assert it
    reproduces the production-measured discrimination:

      - JUNK (141 articles the Localizer rejected as off-topic): >= 70% blocked
        BEFORE any Claude call. Measured: 72.3% (102/141).
      - GOOD (219 articles that produced a published draft): <= 8% blocked.
        Measured: 6.4% (14/219), and those are overwhelmingly genuine
        non-tech mis-acceptances (airlines, customs, finance), not tech loss.

    Bands (not exact equality) tolerate ±a couple of articles from lexicon
    tuning while still catching a real regression (e.g. the 'ai' bug would
    send JUNK-blocked toward ~5%).
    """
    corpus = _load_corpus()
    junk = [a for a in corpus if a["label"] == "JUNK"]
    good = [a for a in corpus if a["label"] == "GOOD"]
    assert len(junk) == 141 and len(good) == 219, "fixture drift"

    junk_blocked = sum(1 for a in junk if not is_relevant(a["title"], a["content"])[0])
    good_blocked = sum(1 for a in good if not is_relevant(a["title"], a["content"])[0])

    junk_rate = junk_blocked / len(junk)
    good_rate = good_blocked / len(good)

    assert junk_rate >= 0.70, f"JUNK block rate regressed to {junk_rate:.1%} (expect ~72%)"
    assert good_rate <= 0.08, f"GOOD loss rate too high at {good_rate:.1%} (expect ~6%)"


# ---------------------------------------------------------------------------
# 4. URL normalisation (regression — pinned pipeline behaviour, unchanged)
# ---------------------------------------------------------------------------


def test_normalize_url_strips_utm() -> None:
    out = normalize_url("https://medias24.com/article?utm_source=twitter&id=42")
    assert out == "https://medias24.com/article?id=42"


def test_normalize_url_strips_trailing_slash() -> None:
    assert normalize_url("https://wamda.com/article/") == normalize_url("https://wamda.com/article")


def test_url_hash_stable_for_equivalent_urls() -> None:
    a = url_hash("https://maddyness.com/x?utm_campaign=foo")
    b = url_hash("https://maddyness.com/x")
    assert a == b
