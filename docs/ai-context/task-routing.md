# Task Routing — Which Context Files to Load

> Load this file at session start. Use it to decide exactly which domain files to load.
> Principle: load the minimum set. Every unnecessary file is wasted tokens.

---

## How to use

1. Identify the task type from the table below.
2. Load ONLY the listed files for that task type.
3. Do not load the full `claude.full.backup.md` or `CLAUDE.md` unless troubleshooting context rules.
4. `CLAUDE.md` (root) is auto-loaded — do not reload it manually.

---

## Task → Context map

| Task type | Load these files |
|---|---|
| **Frontend UI / components / pages** | `docs/ai-context/frontend.md` |
| **Frontend + auth (admin panel)** | `docs/ai-context/frontend.md` + `docs/ai-context/auth.md` |
| **Backend API / routes / schemas** | `docs/ai-context/backend.md` |
| **Backend + database (models, queries)** | `docs/ai-context/backend.md` + `docs/ai-context/database.md` |
| **AI localization / quality gate / prompts** | `docs/ai-context/ai-pipeline.md` |
| **Editing the localizer prompt** | `docs/ai-context/ai-pipeline.md` + explicitly read `backend/app/services/ai/prompts/localizer_v1.md` |
| **Database schema / migrations** | `docs/ai-context/database.md` |
| **Authentication / security** | `docs/ai-context/auth.md` + `docs/ai-context/backend.md` |
| **Infrastructure / env vars / costs** | `docs/ai-context/infrastructure.md` |
| **Deployment / CI/CD / Railway / Vercel** | `docs/ai-context/deployment.md` |
| **Full stack feature (frontend + backend)** | `docs/ai-context/frontend.md` + `docs/ai-context/backend.md` |
| **Product / editorial / scoping decisions** | `docs/ai-context/product.md` |
| **Planning / roadmap / next tasks** | `docs/ai-context/roadmap.md` + `docs/ai-context/active-tasks.md` |
| **Session start / resume work** | `docs/ai-context/active-tasks.md` → then route to domain |
| **Architecture decisions** | `docs/DECISIONS.md` + relevant domain files |
| **Test writing** | Relevant domain file (backend.md or frontend.md) |
| **Debugging a production issue** | `docs/ai-context/infrastructure.md` + relevant domain file |

---

## Never load automatically

These files should only be explicitly requested when directly editing them:

| File | Reason |
|---|---|
| `backend/app/services/ai/prompts/localizer_v1.md` | 52KB — load only when editing the prompt |
| `docs/test-results/` | Raw model output artifacts — historical only |
| `claude.full.backup.md` | 41KB archived backup — reference only |
| `backend/logs/` | Runtime logs — never context-relevant |
| `backend/app/services/ai/cross_model_pipeline.py` | Not in production path (ADR-002) |
| `backend/uv.lock` / `frontend/pnpm-lock.yaml` | Lockfiles — never useful as context |

---

## Recommended session startup sequence

```
1. Read task-memory/current-focus.md            → What am I working on right now?
2. Read task-memory/active-constraints.md       → What's blocking or forbidden?
3. Route to 1-2 domain context files (table above)
4. Read task-memory/recent-decisions.md         → Any decisions that affect this task?
5. Read only the specific files you'll touch
6. Work.
7. Before closing:
   - Update task-memory/current-focus.md        → New state + next action
   - Update task-memory/implementation-status.md → Mark completed sub-tasks
   - Add bugs to task-memory/known-bugs.md      → If any discovered
   - Add debt to task-memory/pending-refactors.md → If any introduced
```

## When to load which memory files

| Memory file | Load when |
|---|---|
| `task-memory/current-focus.md` | Every session start — always |
| `task-memory/active-constraints.md` | Every session start — always |
| `task-memory/recent-decisions.md` | When making decisions or starting new work |
| `task-memory/implementation-status.md` | When planning work or checking what's done |
| `task-memory/pending-refactors.md` | When touching existing code |
| `task-memory/known-bugs.md` | When debugging or reviewing a feature |

---

## Context budget guidance

Target: ≤50K tokens active at any time for a focused session.

| Domain file | Approx tokens |
|---|---|
| `CLAUDE.md` (auto-loaded) | ~2,900 |
| Any single domain file | ~600–900 |
| Two domain files | ~1,400–1,800 |
| Full session startup (CLAUDE.md + 2 domain files + 3 code files) | ~8,000–12,000 |
