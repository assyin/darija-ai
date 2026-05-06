# Active Tasks — DarijaAI

> This file tracks current work in progress. Update it at the end of each session.
> Load this file at the start of every session to resume context quickly.

---

## Currently in progress

### Auth implementation — REFACTOR-03 (next session)
**Goal**: Build `backend/app/core/security.py` from scratch and wire JWT auth on all admin routes.
**Status**: Not started. Repo is now stabilized — this is the next priority.
**Context**: See `docs/ai-context/auth.md` + `docs/ai-context/backend.md` when starting.

---

## Recently completed

### Repository stabilization (2026-05-06)
- Ran 28 unit tests — all passed
- Committed backend API: REST routes, schemas, site_settings model + migration, integration tests (`145d487`)
- Committed frontend skeleton: Next.js 15 RTL public site + admin panel (`fe10508`)
- Fixed 2 context inaccuracies: REFACTOR-03 false claim, active-tasks.md staleness

### Context architecture refactor (2026-05-06)
- CLAUDE.md reduced from 1069 lines / ~17K tokens to 158 lines / ~2.9K tokens
- Domain context files created under `docs/ai-context/`
- Task memory system created under `docs/ai-context/task-memory/`

### AI Localization Pipeline (2026-05-04)
- Haiku 4.5 single-pass production mode (ADR-002)
- A/B/D/E comparison test — results in `docs/test-results/2026-05-04-localizer-comparison/`

---

## Blocked / Pending

| Task | Blocker |
|---|---|
| Worker / APScheduler | Design decision: arq vs direct APScheduler |
| NextAuth wiring | Need Resend API key + magic link template |
| CI/CD pipeline | Need GitHub repo secrets configured |
| Staging env | Need Railway staging service created |

---

## Session handoff notes

**Last session**: Repository stabilization. Committed backend API + frontend skeleton. Fixed context inaccuracies.
**Commits this session**: `145d487` (backend), `fe10508` (frontend).
**Decisions made**: None new.
**Next session**: REFACTOR-03 — build `core/security.py` and wire auth on admin routes (~1 session).

---

> **Protocol**: When ending a session, update this file before closing. Include:
> - What was completed
> - What's next
> - Any new decisions (log in `docs/DECISIONS.md`)
> - Files modified this session
