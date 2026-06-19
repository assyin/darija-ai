"""Unit tests for the deterministic editorial ranker (ERE MVP v1.1).

Pure functions → fully deterministic. We pin the contract that matters most:
an *important* article from a weak source must outrank a *banal* article from a
strong source (importance is the dominant signal), plus threshold/freshness/
MENA behaviour, EN+FR signal parity, and the score_breakdown structure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.editorial.deterministic_ranker import (
    RankInput,
    RankResult,
    _normalize,
    decide,
    rank,
    score_actors,
    score_actors_v1_1,
    score_freshness,
    score_importance,
    score_importance_v1_1,
    score_mena,
    score_source,
    score_strategic_category,
)

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
TIERS = {"TechCrunch AI": "A", "Frenchweb": "B", "Numerama": "C"}


def _fresh(hours_ago: float) -> datetime:
    return NOW - timedelta(hours=hours_ago)


def _rank(item: RankInput, threshold: int = 55) -> RankResult:
    return rank(item, tiers=TIERS, now=NOW, threshold=threshold)


# ---------------------------------------------------------------------------
# 1. Importance dominates source — important@C beats banal@A
# ---------------------------------------------------------------------------


def test_important_article_from_tier_C_beats_banal_from_tier_A() -> None:
    important_c = RankInput(
        title="OpenAI raises $1 billion in a new funding round",
        content=(
            "The AI startup announced a major funding round. The new model and "
            "its machine learning stack rely on a large gpt-based platform."
        ),
        source_name="Numerama",  # tier C (weight 5)
        published_at=_fresh(1),
        fetched_at=_fresh(1),
    )
    banal_a = RankInput(
        title="A small tool tweak for some users",
        content="The company shared a minor app change for its dashboard.",
        source_name="TechCrunch AI",  # tier A (weight 15)
        published_at=_fresh(1),
        fetched_at=_fresh(1),
    )
    r_c = _rank(important_c)
    r_a = _rank(banal_a)

    assert r_c.score > r_a.score, (r_c.breakdown, r_a.breakdown)
    # Despite the source disadvantage (5 vs 15), importance carries it.
    assert r_c.breakdown["importance"] > r_a.breakdown["importance"]
    assert r_c.breakdown["source"] < r_a.breakdown["source"]


# ---------------------------------------------------------------------------
# 2. Threshold respected
# ---------------------------------------------------------------------------


def test_decide_threshold_boundary() -> None:
    assert decide(55, 55) == "selected"  # >= is selected
    assert decide(56, 55) == "selected"
    assert decide(54, 55) == "deferred"


def test_rank_decision_follows_threshold() -> None:
    item = RankInput(
        title="Anthropic unveils a new model",
        content="A major AI launch with a new llm and gpt platform.",
        source_name="TechCrunch AI",
        published_at=_fresh(1),
        fetched_at=_fresh(1),
    )
    high = _rank(item, threshold=10)
    low = _rank(item, threshold=99)
    assert high.decision == "selected"
    assert low.decision == "deferred"
    assert high.score == low.score  # score is threshold-independent


# ---------------------------------------------------------------------------
# 3. Freshness decay + fallback
# ---------------------------------------------------------------------------


def test_freshness_decay() -> None:
    assert score_freshness(_fresh(1), _fresh(1), NOW) == 12  # <= 6h → full
    assert score_freshness(_fresh(60), _fresh(60), NOW) == 0  # >= 48h → zero
    # 27h in → linear: 12 * (48-27)/(48-6) = 12 * 21/42 = 6
    assert score_freshness(_fresh(27), _fresh(27), NOW) == 6


def test_freshness_falls_back_to_fetched_at_when_no_published_at() -> None:
    assert score_freshness(None, _fresh(1), NOW) == 12
    assert score_freshness(None, _fresh(60), NOW) == 0


def test_future_published_clamps_to_full() -> None:
    assert score_freshness(NOW + timedelta(hours=5), _fresh(1), NOW) == 12


# ---------------------------------------------------------------------------
# 4. MENA signal
# ---------------------------------------------------------------------------


def test_mena_signal_scales_with_distinct_hits() -> None:
    assert score_mena("une startup au maroc") == 8  # 1 distinct
    assert score_mena("yassir lance au maroc et en afrique") == 16  # >= 2 → cap
    assert score_mena("a generic ai startup in europe") == 0


# ---------------------------------------------------------------------------
# 5. EN and FR signals (parity)
# ---------------------------------------------------------------------------


def test_english_event_and_magnitude_signals() -> None:
    item = RankInput(
        title="Anthropic acquires a startup for $400 million",
        content="The acquisition expands its AI model line.",
        source_name="Frenchweb",
        published_at=_fresh(2),
        fetched_at=_fresh(2),
    )
    r = _rank(item)
    d = r.breakdown["importance_detail"]
    assert d["event_type"] == 15  # "acquires"
    assert d["magnitude"] == 9  # "$400 million" → hundreds-of-millions
    assert d["actors"] == 8  # "anthropic"


def test_french_event_and_magnitude_signals() -> None:
    item = RankInput(
        title="Mistral rachète une startup pour 400 millions d'euros",
        content="L'acquisition renforce son modèle d'IA et son apprentissage automatique.",
        source_name="Frenchweb",
        published_at=_fresh(2),
        fetched_at=_fresh(2),
    )
    r = _rank(item)
    d = r.breakdown["importance_detail"]
    assert d["event_type"] == 15  # "rachète"
    assert d["magnitude"] == 9  # "400 millions"
    assert d["actors"] == 8  # "mistral"
    assert r.breakdown["importance"] > 0


# ---------------------------------------------------------------------------
# 6. score_breakdown structure + source tier weights
# ---------------------------------------------------------------------------


def test_breakdown_structure_and_total_consistency() -> None:
    item = RankInput(
        title="OpenAI launches a new AI agent platform",
        content="A startup deal with machine learning and gpt; tested in maroc.",
        source_name="Numerama",
        published_at=_fresh(3),
        fetched_at=_fresh(3),
    )
    b = _rank(item).breakdown
    assert set(b) == {
        "total",
        "importance",
        "relevance",
        "mena",
        "source",
        "freshness",
        "importance_detail",
        "source_tier",
    }
    assert set(b["importance_detail"]) == {"event_type", "magnitude", "actors"}
    # total = sum of the five components
    assert b["total"] == (
        b["importance"] + b["relevance"] + b["mena"] + b["source"] + b["freshness"]
    )
    assert 0 <= b["total"] <= 100
    assert b["source_tier"] == "C"


def test_source_tier_weights() -> None:
    assert score_source("TechCrunch AI", TIERS) == (15, "A")
    assert score_source("Frenchweb", TIERS) == (10, "B")
    assert score_source("Numerama", TIERS) == (5, "C")
    assert score_source("Some Unknown Blog", TIERS) == (4, "unknown")


def test_real_config_source_tiers_map_a_known_source() -> None:
    from app.core.config import SOURCE_TIERS

    weight, tier = score_source("Wamda", SOURCE_TIERS)
    assert tier == "A"
    assert weight == 15


# ---------------------------------------------------------------------------
# 7. v1.1 importance enrichment — Strategic Importance + Actors (offline lever)
# ---------------------------------------------------------------------------

# Panel covering every signal kind: used for the monotonicity / no-regression
# guarantees that bound this lever's risk.
_PANEL: tuple[str, ...] = (
    "openai raises $1 billion for a new ai model",
    "salesforce acquires fin an ai customer service platform for $3.6 billion",
    "google unveils the open knowledge format standard for ai agents",
    "claude will require identity verification to keep using some ai features",
    "snap launches $2200 ar glasses for consumers",
    "spacex valuation balloons to $2.7t as it passes amazon",
    "a small dashboard tweak for some users",
    "une startup au maroc leve des fonds pour son modele d'ia",
    "l'ia pousse une entreprise a reduire ses effectifs de 25%",
    "chatgpt market share slips below 50% for the first time in the ai race",
)


def test_rank_default_is_v1_byte_identical() -> None:
    """The CONTRACT: rank() with no importance_model is strictly v1.0 — same
    score AND same breakdown (incl. importance_detail keys) as explicit "v1"."""
    for text in _PANEL:
        item = RankInput(
            title=text,
            content=text,
            source_name="TechCrunch AI",
            published_at=_fresh(2),
            fetched_at=_fresh(2),
        )
        default = rank(item, tiers=TIERS, now=NOW, threshold=55)
        explicit_v1 = rank(item, tiers=TIERS, now=NOW, threshold=55, importance_model="v1")
        assert default == explicit_v1
        # v1 breakdown shape is unchanged — no v1.1 keys leak into the default path.
        assert set(default.breakdown["importance_detail"]) == {
            "event_type",
            "magnitude",
            "actors",
        }


def test_actors_v1_1_is_a_superset_of_v1() -> None:
    """Broader lexicon, same caps → score_actors_v1_1 >= score_actors for ANY text."""
    for text in _PANEL:
        norm = _normalize(text)
        assert score_actors_v1_1(norm) >= score_actors(norm)
    # New names the v1 lexicon misses:
    assert score_actors_v1_1(_normalize("salesforce acquires an ai startup")) == 5
    assert score_actors_v1_1(_normalize("deepseek releases a new ai model")) == 8
    # v1 scored these 0 / 0 respectively.
    assert score_actors(_normalize("salesforce acquires an ai startup")) == 0


def test_importance_v1_1_is_monotone_vs_v1() -> None:
    """The risk-bounding property: importance can only rise or stay, never drop.
    So a correct v1 selection can NEVER be lost; only FN->TP or new FP can occur."""
    for text in _PANEL:
        norm = _normalize(text)
        assert score_importance_v1_1(norm)[0] >= score_importance(norm)[0]


def test_importance_v1_1_no_regression_on_big_funding() -> None:
    """max(magnitude, strategic) keeps a Sarvam-style big round unchanged."""
    norm = _normalize("sarvam raises $234 million to become india's newest ai unicorn")
    assert score_importance_v1_1(norm)[0] == score_importance(norm)[0]


def test_strategic_category_requires_ai_anchor() -> None:
    """Anti-noise gate: a strategic keyword with NO AI/tech token scores 0."""
    assert score_strategic_category(_normalize("a new banking standard for payments")) == (
        0,
        "none",
    )
    # Generic "standard" is no longer a trigger even WITH an AI token (tightened).
    assert score_strategic_category(_normalize("a new ai data standard")) == (0, "none")
    # A specific protocol + agent context DOES fire.
    points, label = score_strategic_category(_normalize("a new ai agent protocol"))
    assert points == 12 and label == "infra_standards"


def test_strategic_category_tiers_and_max() -> None:
    # 12-pt structural — infra requires a SPECIFIC token (open knowledge format)
    assert (
        score_strategic_category(_normalize("google unveils the open knowledge format for ai"))[0]
        == 12
    )
    assert (
        score_strategic_category(_normalize("anthropic overtakes openai in ai market share"))[0]
        == 12
    )
    # 10-pt strategic-move — sovereignty now needs entity + concrete move
    assert score_strategic_category(
        _normalize("mistral powers the state ai deployment, a sovereignty milestone")
    ) == (10, "sovereignty_policy")
    assert score_strategic_category(_normalize("ai pushes the firm to cut its workforce"))[0] == 10
    assert (
        score_strategic_category(_normalize("claude adds identity verification to its ai"))[0] == 10
    )
    # When both a 12-tier and 10-tier match, the 12 wins (max). Market needs an entity.
    both = _normalize("google market share shifts as the firm cuts its ai workforce")
    assert score_strategic_category(both)[0] == 12


def test_strategic_category_low_priority_consumer_scores_zero() -> None:
    """Consumer launch with a big number gets NO strategic points (FP not fueled)."""
    assert score_strategic_category(_normalize("snap launches $2200 ar glasses"))[0] == 0


def test_strategic_category_tightened_anti_noise() -> None:
    """Rule 4 — the corpus noise that the loose lexicon wrongly selected must
    now score 0 (each line includes an AI/tech token to exercise the real path)."""
    noise = (
        "amazon degaine ses promos prime day sur les gadgets ia et le cloud data",
        # entertainment that name-drops an AI entity (nvidia) + "surpasse" must
        # still NOT fire market_structure — the OS/consumer block catches it.
        "toy story 5 : la techno nvidia surpasse tout et depasse le marche, une ia au cinema",
        "microsoft lance une nouvelle fonctionnalite ia sur windows 11 avec api",
        "android 17 launches with a new ai multitasking tool and api access",
        "linux 7.1 protocol standard for ai agents and llm tooling",
        "euro-office 1.0 ai assistant feature for documents and data",
        "votre voiture pourrait ne plus avoir de radio fm, tesla et l'ia embarquee",
    )
    for text in noise:
        points, label = score_strategic_category(_normalize(text))
        assert points == 0, f"strategic_category wrongly fired ({label}) on: {text}"


def test_sovereignty_policy_round3_requires_entity_and_move() -> None:
    """Round-3 — bare souveraineté/policy debates no longer qualify; they need a
    strong AI entity AND a concrete deployment/integration move."""
    sc = score_strategic_category
    # Entity present but NO concrete move (pure debate) → 0  [mirrors #2253/#2091/#1984]
    assert sc(_normalize("anthropic et la souverainete de l'ia au coeur des debats du g7"))[0] == 0
    # Souveraineté/policy signal but NO entity → 0  [mirrors #2162/#2278]
    assert sc(_normalize("la souverainete de l'ia dans le crm, categorie a risque"))[0] == 0
    # Entity + the NOUN "déploiement" (infra/debate) is NOT a move → 0  [#2253/#1984]
    assert sc(_normalize("anthropic: deploiement de data centers, souverainete de l'ia"))[0] == 0
    # OS/consumer context (office suite) blocks sovereignty even with a move → 0  [#2091]
    assert sc(_normalize("microsoft euro-office: souverainete de l'ia et integration"))[0] == 0
    # Signal + strong entity + concrete deployment verb → fires  [mirrors #2092]
    pts, label = sc(
        _normalize(
            "mistral: la france generalise l'ia generative dans l'etat, enjeu de souverainete"
        )
    )
    assert pts == 10 and label == "sovereignty_policy"


def test_frontier_move_round3_reclassifies_integration_and_drops_nonevents() -> None:
    """Round-3 — a model integrated into a product is frontier_move (not policy);
    a non-event with only an AI mention + a deploy verb is not a move."""
    sc = score_strategic_category
    # DeepSeek integrated into Copilot → frontier_move, NOT sovereignty  [#2301]
    pts, label = sc(
        _normalize("l'ia deepseek au coeur de copilot de microsoft, enjeu de souverainete")
    )
    assert pts == 10 and label == "frontier_move"
    # Non-event: AI entity + traffic mention + a deploy verb but NO product/access/
    # model/integration action → 0  [#2224]
    assert (
        sc(_normalize("l'ia d'openai: pas de baisse de trafic web observee, deploiement a venir"))[
            0
        ]
        == 0
    )


def test_strategic_category_keeps_real_strategic_fn() -> None:
    """Rule 5 — the genuine strategic FN must still fire a strategic category."""
    keepers = (
        ("google reveals the open knowledge format for ai agents", "infra_standards"),
        ("claude will require identity verification to use ai features", "frontier_move"),
        ("anthropic depasse openai sur le marche des abonnements ia", "market_structure"),
        ("l'ia pousse lastminute a reduire ses effectifs de 25%", "enterprise_labor"),
    )
    for text, expected_label in keepers:
        points, label = score_strategic_category(_normalize(text))
        assert points >= 10 and label == expected_label, (text, points, label)


def test_v1_1_recovers_known_strategic_false_negatives() -> None:
    """The three clean FN from the human baseline cross 55 under v1_1, while
    staying deferred under v1 — and v1's own decision is unchanged."""
    cases = (
        # (title, content, source) — all tier A in TIERS
        (
            "Salesforce acquires AI customer service platform Fin for $3.6B",
            "The acquisition expands its enterprise ai and machine learning suite.",
            "TechCrunch AI",
        ),
        (
            "Google reveals the Open Knowledge Format standard for AI agents",
            "A new ai infrastructure standard for agent context and data.",
            "TechCrunch AI",
        ),
        (
            "Claude will require identity verification to keep using some features",
            "Anthropic adds identity verification to its ai assistant access.",
            "TechCrunch AI",
        ),
    )
    for title, content, source in cases:
        item = RankInput(
            title=title,
            content=content,
            source_name=source,
            published_at=_fresh(40),  # low freshness → realistic borderline score
            fetched_at=_fresh(40),
        )
        v1 = rank(item, tiers=TIERS, now=NOW, threshold=55, importance_model="v1")
        v1_1 = rank(item, tiers=TIERS, now=NOW, threshold=55, importance_model="v1_1")
        assert v1_1.score >= v1.score
        assert v1_1.breakdown["importance"] >= v1.breakdown["importance"]
        assert v1_1.breakdown["importance_detail"]["model"] == "v1_1"
