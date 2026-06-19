# Editorial Ranking Engine — v1.1 Importance Lever (Calibration Notes)

> **Status:** SHADOW-default, **observe-only** — NOT enforced. `rank()` default stays v1.0.
> Validated offline against the live production pending corpus (READ-ONLY exports).

## What this lever does

The deterministic ranker scores each pending article `/100`:

```
importance 0-35 · relevance 0-22 · MENA 0-16 · source 0-15 · freshness 0-12   (threshold 55)
```

The **"Strategic Importance + Actors" (v1_1)** lever enriches ONLY the `importance` axis:

```
importance_v1_1 = min(35, event_type + max(magnitude, strategic_category) + actors_v1_1)
```

- `max(magnitude, strategic_category)` — a new path to importance points (strategic
  recognition) **without removing** the existing magnitude path → no regression on big
  funding rounds (e.g. Sarvam). The 0-12 slot is shared.
- `strategic_category` (0-12) — recognises editorial value the event/magnitude signals
  miss: `infra_standards`, `market_structure`, `sovereignty_policy`, `enterprise_labor`,
  `frontier_move`. Each carries a strong gate (see below).
- `actors_v1_1` (0-8) — broader actor lexicon (adds Salesforce, DeepSeek, Cohere, etc.).

**Monotonicity guarantee:** `importance_v1_1 >= importance_v1` for any input → a correct v1
selection can never be lost; only false-negative recovery or new false-positives can occur.
This bounds the lever's risk and is unit-tested.

## How it is wired (observe-only)

- `rank(importance_model="v1")` is the **default** and is byte-identical to v1.0
  (locked by `test_rank_default_is_v1_byte_identical`).
- `v1_1` is selected ONLY by the SHADOW recorder (`shadow_recorder.py`) and the offline
  comparison script. The recorder writes ONLY the decoupled `editorial_*` columns, never
  `processing_status`, never a publication, never an LLM, and is fully fail-soft.
- The recorder runs in `process_one` ONLY when `editorial_ranking_shadow_enabled` is ON
  (default **OFF**). It is a one-line no-op when OFF.
- **No enforce:** nothing makes `editorial_decision` affect what the pipeline localizes or
  publishes.

## Calibration history (3 rounds, offline-validated)

| Round | Change | Result on live corpus |
|--|--|--|
| Loose | strategic_category with broad lexicon | Over-fired on consumer/OS/shopping noise (Prime Day, Toy Story, Windows/Linux/Android); +29 volume, 3+ new FP → **NO-GO** |
| R2 | Removed generic tokens; `market_structure`/`frontier_move` require a strong AI entity; OS/consumer block | Noise eliminated, 0 new FP on the boundary baseline; +15 volume |
| **R3 (final)** | `sovereignty_policy` gated = signal **+** AI entity **+** concrete deployment/integration VERB **+** not OS/consumer; `frontier_move` reordered before sovereignty so product integrations (DeepSeek→Copilot) classify correctly; non-events dropped | See metrics below |

### Final metrics (R3, corpus = 361 live pending; human baseline N=61)

| | v1 | v1_1 (R3) |
|--|--|--|
| Precision | 0.59 | **0.69** |
| Recall | 0.52 | **0.81** |
| Human agreement | 0.57 | **0.72** |
| New labelled FP | — | **0** |
| Selected (corpus) | 70 | 82 (Δ +12) |
| Regressions (selected→deferred) | — | **0** |

9 genuine strategic false-negatives recovered (Salesforce/Fin M&A, Google Open Knowledge
Format, Anthropic>OpenAI market share, lastminute labor, Visa×OpenAI agentic payments,
Aive×Nvidia, France gen-AI deployment, etc.) with zero confirmed new false positives.

### Known residual (minor, out of this lever's scope)

- `#2290` (an AMD GPU benchmark) slips through `market_structure` via a Nvidia mention +
  "surpasse". A future pass can extend the consumer/OS exclusion to hardware-review terms
  (`radeon|geforce|rx \d{4}|benchmark`). Single-article impact.

## Offline validation method (READ-ONLY, no prod writes)

`python -m app.scripts.compare_importance_shadow` ranks the pending corpus with both
`v1` and `v1_1`, cross-references the frozen human-baseline labels, and prints
newly-selected / regressions / precision / recall. Validation exported the prod pending
rows read-only (`COPY ... TO STDOUT`) into a throwaway local Postgres; production was
never written to.

## Not in scope / not done

- No MENA change, no dedup, no digest penalty, no threshold change, no `process_pending`
  change, no enforce, no deploy, no flag activation.
