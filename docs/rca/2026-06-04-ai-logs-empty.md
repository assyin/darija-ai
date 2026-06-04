# RCA — `ai_logs` table empty in production

**Incident**: 2026-06-04
**Author**: Yassine / Claude (CTO mode)
**Severity**: P1 — cost observability broken (CLAUDE.md mandates "$5/day Sentry alert"; impossible to fire)
**Status**: ✅ Root cause identified · 🔧 Fix designed · ⏳ Pending deploy

---

## Summary

The `ai_logs` table has been empty since production launch (2026-05-26) despite **50 successful localizations + 50 successful French translations + ~50 image generations + N proofreader runs**. Cost tracking, daily-spend alerting, and per-article cost attribution have been silently non-functional.

The table was created by the initial Alembic migration (`20260503_1912_a40f4ff284f0_create_initial_schema.py`, commit `cb76bd2`) but **no code was ever written that inserts into it**. The model exists, the schema is correct, the AI clients compute the cost — but the cost is only emitted to structlog, never persisted.

---

## Detection

User question during 5-year architecture planning:
> "Et si dans 2 ans TitritAI a 10 000+ articles…"

Triggered a prod audit:

```sql
SELECT provider, model, COUNT(*), SUM(cost_usd)
FROM ai_logs WHERE success=true GROUP BY 1,2;
-- 0 rows
```

Cross-check on `articles` confirmed the queries were definitely happening:

```sql
SELECT COUNT(*) FILTER (WHERE content_fr IS NOT NULL) FROM articles;
-- 50 (every article has a French translation → translator ran 50 times)
```

**Conclusion**: The AI pipeline ran, costs were incurred, but nothing was recorded.

---

## Evidence

### 1. Model is defined and registered

`backend/app/models/ai_log.py` defines `AILog(SQLModel, table=True)` with all expected columns.

`backend/app/models/__init__.py:11` registers it in `__all__`.

`backend/alembic/versions/20260503_1912_a40f4ff284f0_create_initial_schema.py` creates the table — the prod table exists.

### 2. Cost is computed but never persisted

`backend/app/services/ai/claude_client.py:141` calls `compute_cost(model, in_tok, out_tok)` and emits a `structlog` event `ai.claude.request_completed` with `cost_usd=str(cost)` — but the value never reaches the database.

`backend/app/services/ai/openai_client.py:140` — identical pattern.

`backend/app/services/images/replicate_client.py:122` — identical pattern for image generation cost.

### 3. Codebase-wide grep proves no INSERT exists

```text
$ grep -rn "AILog(\|INSERT INTO ai_logs\|session.add(.*AILog" backend/
backend/app/models/ai_log.py:25:class AILog(SQLModel, table=True):
```

A single hit — the class definition. **Zero call sites construct or persist an `AILog` row.**

---

## Root cause

**The model was scaffolded during the initial schema PR but the writer code was never authored.** No git commit ever added an `AILog(...)` insert.

The work was likely deferred behind the "make it work first, observability later" line and forgotten — a classic *aspirational schema* failure mode. The structlog cost emission gave the false impression that observability was wired (logs look right in dev), masking the persistence gap.

### Contributing factors

| Factor | Effect |
|---|---|
| Cost is logged to **structlog** at every callsite | Looks "tracked" in console / Sentry breadcrumbs → false confidence |
| No alert was ever configured against `ai_logs` | A missing-data condition is hard to detect without a baseline expectation |
| `Sentry alert if daily spend > $5` (CLAUDE.md §5) is a written rule, not implemented code | Nothing forced the team to wire it |
| Tests cover Localizer/Translator behavior, not their side-effects on `ai_logs` | Type-system happy, runtime silent |
| `AILog` model registered in `__init__.py` → IDE autocomplete works → looks healthy | Imports succeed; nothing throws |

### Why structlog logging was insufficient

The fields land in stdout → Docker logs → ephemeral. With Hetzner single-node deploy + no log aggregation (no Loki / no Datadog / no Sentry log sink for INFO events), they evaporate at container restart. **No cumulative cost view ever existed.**

---

## Impact

| Dimension | Impact |
|---|---|
| **Cost visibility** | Zero historical cost data. Cannot answer "what did we spend last month?" |
| **Budget alerts** | The `$5/day` ceiling in CLAUDE.md §5 cannot fire — there's no data source |
| **Per-article cost attribution** | Cannot identify expensive articles or model-mix inefficiencies |
| **Architecture decisions** | The Option A/B/C analysis (multilingual roadmap) had to use **estimated** per-article costs rather than measured ones |
| **Financial risk** | At ~50 articles, exposure is ~$1-3 — negligible. **But the risk grows linearly with volume**, and the user is about to scale to multilingual + MSA |

---

## Fix design

### Strategy: layered wrapper, not callsite edits

A new `LoggingLLMProvider` decorator implements the existing `LLMProvider` Protocol, wraps any concrete provider (`ClaudeClient`, `OpenAIClient`), and persists an `AILog` row after every `complete()` call — success or failure.

```python
class LoggingLLMProvider:
    """LLMProvider that persists every call to ai_logs.

    Wraps an inner provider transparently. Fail-soft: a DB error during
    log persistence does NOT propagate — the AI call's result/error is
    always honoured. Structured-log warnings surface persistence failures
    so they remain debuggable.

    raw_article_id is read from metadata["raw_article_id"] when present;
    otherwise the row is logged with raw_article_id=NULL (still useful
    for global cost totals).
    """

    def __init__(self, inner: LLMProvider, session_factory): ...

    async def complete(self, *, system, user, model=None, max_tokens=4096,
                       temperature=0.7, metadata=None) -> LLMResponse:
        raw_article_id = _extract_raw_article_id(metadata)
        try:
            response = await self._inner.complete(...)
        except Exception as exc:
            await self._persist_failure(model=..., raw_article_id=..., error=str(exc))
            raise
        await self._persist_success(response, raw_article_id=raw_article_id)
        return response
```

A standalone `persist_ai_log(...)` helper covers the **non-LLM** code paths
(Replicate image generation, Proofreader's direct OpenAI client).

### Wiring change (minimal)

| File | Change | Lines |
|---|---|---|
| `backend/app/services/ai/ai_logging.py` | **NEW** — `LoggingLLMProvider` + `persist_ai_log` | +~150 |
| `backend/app/services/ai/translator.py` | Constructor takes `LLMProvider` (Protocol), `translate()` gains `raw_article_id` kw-only param | ~8 |
| `backend/app/services/pipeline/article_processor.py` | `from_settings()` wraps provider in `LoggingLLMProvider`; pipeline calls `persist_ai_log` after image gen; passes `raw.id` to translator | ~20 |
| `backend/app/services/ai/proofreader.py` | Add `persist_ai_log(...)` call after `chat.completions.create()` | ~8 |

**Total**: ~190 lines, 1 new module, 3 minor wiring changes. No breaking API surface.

### Why a wrapper, not callsite INSERTs

| Approach | Pros | Cons |
|---|---|---|
| **INSERT in each service (Localizer, Translator…)** | Simple, DRY-violating | Every new service must remember to write. Easy to forget. |
| **INSERT in `ClaudeClient.complete()` directly** | One place | Couples HTTP client to DB. Breaks layering (CLAUDE.md §3: "utils stateless, services framework-agnostic"). |
| ✅ **Decorator wrapping `LLMProvider`** | Single point of truth, respects layering, opt-in by wiring | One extra abstraction |

### Fail-soft policy

A DB write error during `_persist_success` must **never** propagate to the caller. The AI call already succeeded — failing the user request because logging failed would be worse than missing one log row. The wrapper catches `Exception` around the DB write, emits a `structlog` warning with full context, and continues. The same applies to `_persist_failure`.

This preserves the system's existing fail-soft behaviour (the Translator is already fail-soft at the pipeline level — failed translation doesn't block the draft).

---

## Verification plan (post-fix)

### Local

1. Apply fix on `fix/ai-logs-cost-tracking` branch
2. `make backend-test` — existing tests pass
3. New unit tests:
   - `LoggingLLMProvider` records a row on success
   - `LoggingLLMProvider` records a row with `success=false` on failure
   - DB error during persist does NOT block the response
   - `raw_article_id` flows from metadata to DB column
4. `mypy --strict` clean on the new module

### Production verification

After deploy, run a single article through the pipeline:

```sql
-- Should be 0 → some positive number after a new article runs
SELECT COUNT(*) FROM ai_logs WHERE created_at > NOW() - INTERVAL '10 minutes';

-- Should show both Localizer (claude-haiku-4-5) and Translator (claude-haiku-4-5)
-- and possibly Replicate (black-forest-labs/flux-schnell)
SELECT provider, model, success, COUNT(*), SUM(cost_usd)
FROM ai_logs
WHERE created_at > NOW() - INTERVAL '10 minutes'
GROUP BY 1, 2, 3;

-- raw_article_id propagation check
SELECT COUNT(*) FROM ai_logs WHERE raw_article_id IS NOT NULL;
```

### Long-term verification (will not be done in this PR)

Once `ai_logs` is reliably populated, **then** the CLAUDE.md §5 alert can be implemented:

```sql
-- Daily-spend ceiling check (~$5/day)
SELECT SUM(cost_usd) FROM ai_logs
WHERE created_at > NOW() - INTERVAL '24 hours';
```

Wired to a cron + Sentry capture-message, or to a Grafana panel later. **Out of scope for this PR.**

---

## Lessons / hardening

1. **Aspirational schemas must come with a writer test**: any new `table=True` model in the same PR should have at least one INSERT in code + a test that asserts the row exists. This is a CLAUDE.md addition worth proposing.
2. **structlog "cost_usd" event ≠ persisted cost**: rename in-flight log key to `cost_usd_estimate` to prevent the same confusion in future incident reviews.
3. **Make the alert query exist alongside the rule**: every numeric SLO in CLAUDE.md (cost, latency, error rate) needs a corresponding SQL query and a placeholder cron job, even if disabled. The query itself acts as a contract.

---

## Out-of-scope (tracked separately)

- **Implementing the daily $5 spend alert** — requires `ai_logs` populated first (this PR enables it; the alert itself is its own concern).
- **Backfilling historical costs** — not possible; the data was never captured. Going forward only.
- **Proofreader's direct AsyncOpenAI usage** — should route through `OpenAIClient` for consistency. Small follow-up. Logged for the Phase 0 backlog.
- **Cross-model pipeline cost accounting** (`cross_model_pipeline.py:84`) — `self.total_cost` is in-memory only. Same fix pattern applies; preserved for future PR if/when that pipeline is reactivated (currently not in production per ADR-002).
