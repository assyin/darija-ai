# Recent Decisions

> Update: when a decision is made that affects code, tooling, or architecture.
> Rule: entries stay here until formalized in docs/DECISIONS.md or implemented + stable.
> Entries older than 30 days with no open follow-up: move to docs/DECISIONS.md and delete here.

---

## Active decisions (implement or validate these)

### [2026-05-25] D1 — Worker = arq only (no APScheduler)
**Decision**: Use arq for both the job queue and the periodic scheduler via its native `cron_jobs`. No APScheduler dependency added.
**Why**: arq is already installed; its `cron()` covers periodic triggers (fetch/30min, process/10min, retry/hourly), so a second scheduler would be a redundant dependency (violates "no new dep" rule).
**Status**: Implemented (P0-A). `app/workers/settings.py` `WorkerSettings` boots 4 jobs + 3 cron, Redis-connected. Verified worker starts.
**Follow-up**: None open.

### [2026-05-06] Admin auth — email + password, single-owner, no hashing (MVP)
**Decision**: Backend admin auth uses static email + password validated against env vars (`ADMIN_EMAIL`, `ADMIN_PASSWORD: SecretStr`). No DB users. No refresh tokens. No roles. No password hashing yet. JWT HS256, 1h expiry.
**Why**: Solo founder MVP. Complexity of NextAuth + magic link blocked on Resend API key. Fastest path to a secured admin API. Password hashing deferred until staging has real traffic risk.
**Status**: Implemented and committed (`d247de3`). Rate limiting added `49e7450`. **Auth layer is production-ready for MVP.**
**Follow-up**: Add password hashing (bcrypt via passlib) before first external collaborator gets access.

### [2026-05-06] Context architecture — modular docs/ai-context/ system
**Decision**: Split CLAUDE.md (17K tokens) into domain files (~700 tokens each). Created `.claudeignore`.
**Why**: Reduce per-session token load by ~76%. Improve session stability.
**Status**: Implemented and committed (`5846c89`). Validate over next 5 sessions.

### [2026-05-06] pytest asyncio scope → session-level
**Decision**: Set `asyncio_default_fixture_loop_scope = "session"` in `pyproject.toml`.
**Why**: Avoids per-test event loop teardown overhead in integration tests with shared DB connections.
**Status**: Committed (`145d487`). ✅ Stable.

### [2026-05-06] localizer_v1.md prompt extended (+107 lines) — now frozen
**Decision**: Extended the production localizer prompt in-place before its first prod commit.
**Why**: Addresses failure modes seen in review. Acceptable because it had not yet shipped.
**Status**: Committed (`145d487`). `localizer_v1.md` is now frozen — next change must be `localizer_v2.md`.
**Follow-up**: Run 3 sample articles through the updated prompt before marking fully stable.

### [2026-05-04] ADR-002 — Haiku 4.5 single-pass for production
**Decision**: Haiku 4.5 default, Sonnet 4.6 opt-in via `model=` param. No multi-model pipeline in prod.
**Why**: Cost ($5/mo vs $20/mo), human-in-the-loop is the QA layer, GPT RTL issues.
**Status**: Finalized. See docs/DECISIONS.md for full rationale.
**Follow-up**: None open.

---

## Pending decisions (needs resolution)

| Decision needed | Context | Priority |
|---|---|---|
| Distribution order: LinkedIn first, Meta, or newsletter? | Distribution not yet built | MEDIUM |
| Staging env: Railway preview or manual? | No staging yet | MEDIUM |
| Token storage in frontend: cookie vs localStorage | Needed for REFACTOR-02 Phase B admin login | MEDIUM |

---

*Last updated: 2026-05-06 (REFACTOR-03b follow-up closed)*
