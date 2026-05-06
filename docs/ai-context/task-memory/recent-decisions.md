# Recent Decisions

> Update: when a decision is made that affects code, tooling, or architecture.
> Rule: entries stay here until formalized in docs/DECISIONS.md or implemented + stable.
> Entries older than 30 days with no open follow-up: move to docs/DECISIONS.md and delete here.

---

## Active decisions (implement or validate these)

### [2026-05-06] pytest asyncio scope → session-level
**Decision**: Set `asyncio_default_fixture_loop_scope = "session"` in `pyproject.toml`.
**Why**: Avoids per-test event loop teardown overhead in integration tests with shared DB connections.
**Status**: Applied, not yet committed.

### [2026-05-06] Context architecture — modular docs/ai-context/ system
**Decision**: Split CLAUDE.md (17K tokens) into domain files (~700 tokens each). Created `.claudeignore`.
**Why**: Reduce per-session token load by ~76%. Improve session stability.
**Status**: Implemented. Validate over next 5 sessions.

### [2026-05-06] localizer_v1.md prompt extended
**Decision**: Added ~107 lines to the production localizer prompt.
**Why**: Addresses failure modes seen in review (details in the prompt file itself).
**Status**: Unstaged. Needs commit + validation against sample articles.
**Follow-up**: Run 3 sample articles through the updated prompt before marking stable.

### [2026-05-04] ADR-002 — Haiku 4.5 single-pass for production
**Decision**: Haiku 4.5 default, Sonnet 4.6 opt-in via `model=` param. No multi-model pipeline in prod.
**Why**: Cost ($5/mo vs $20/mo), human-in-the-loop is the QA layer, GPT RTL issues.
**Status**: Finalized. See docs/DECISIONS.md for full rationale.
**Follow-up**: None open.

---

## Pending decisions (needs resolution)

| Decision needed | Context | Priority |
|---|---|---|
| Worker entrypoint: `arq` queue vs direct APScheduler | Currently using scripts manually | HIGH |
| Frontend-to-backend API integration approach | Mock data in many frontend pages | HIGH |
| Distribution order: LinkedIn first, Meta, or newsletter? | Distribution not yet built | MEDIUM |
| Staging env: Railway preview or manual? | No staging yet | MEDIUM |

---

*Last updated: 2026-05-06*
