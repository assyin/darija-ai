# Context Architecture Refactor — Final Report

**Date**: 2026-05-06 · **Scope**: Full repository context optimization

---

## Estimated token savings

### Before refactor

| Source | Tokens | Notes |
|---|---|---|
| `CLAUDE.md` (auto-loaded) | ~17,000 | 1069 lines, 41KB — loaded every session |
| `backend/logs/` (if accidentally read) | ~45,000 | 4 large log files totaling 1MB+ |
| `localizer_v1.md` (if read for context) | ~20,000 | 52KB prompt file |
| `docs/test-results/` (if read) | ~19,000 | 50KB of model output artifacts |
| `claude.full.backup.md` (if read) | ~17,000 | Duplicate of old CLAUDE.md |
| **Baseline per session (just CLAUDE.md)** | **~17,000** | |

### After refactor

| Source | Tokens | Notes |
|---|---|---|
| `CLAUDE.md` (auto-loaded) | ~2,900 | 158 lines — minimal, production-oriented |
| Domain file (per task) | ~700 | Average per domain context file |
| `active-tasks.md` (session start) | ~500 | Session resume context |
| **Baseline per session** | **~4,100** | CLAUDE.md + active-tasks + 1 domain file |
| **Full stack session (2 domain files)** | **~5,500** | CLAUDE.md + active-tasks + frontend + backend |

### Net savings

| Metric | Value |
|---|---|
| Per-session base reduction | **~12,900 tokens saved** (~76%) |
| Dangerous files now blocked | 10 file categories in `.claudeignore` |
| Highest-risk file removed from auto-load | `localizer_v1.md` (52KB / ~20K tokens) |
| Backup file blocked | `claude.full.backup.md` (~17K tokens) |
| Log directory blocked | `backend/logs/` (~45K tokens across files) |

At Sonnet 4.6 pricing ($3/1M input tokens), each 12,900 token session saving = **~$0.039/session**. Across 50 sessions/month: **~$1.95/month saved**, plus dramatically better response quality from focused context.

---

## Highest-risk context bottlenecks (resolved)

| Risk | File | Size | Resolution |
|---|---|---|---|
| CRITICAL | `backend/app/services/ai/prompts/localizer_v1.md` | 52KB / ~20K tokens | Blocked in `.claudeignore` |
| CRITICAL | `backend/logs/sanity_run.log` | 600KB | Entire `backend/logs/` blocked |
| HIGH | `claude.full.backup.md` | 41KB / ~17K tokens | Blocked in `.claudeignore` |
| HIGH | Old `CLAUDE.md` | 41KB / ~17K tokens | Replaced with 7.7KB version |
| HIGH | `docs/test-results/` | 50KB of .md files | Blocked in `.claudeignore` |
| MEDIUM | `frontend/tsconfig.tsbuildinfo` | 266KB | Blocked in `.claudeignore` |
| MEDIUM | `frontend/pnpm-lock.yaml` | 227KB | Blocked in `.claudeignore` |
| MEDIUM | `backend/uv.lock` | 167KB | Blocked in `.claudeignore` |
| MEDIUM | `backend/app/services/ai/cross_model_pipeline.py` | 14KB | Blocked (not in prod path) |
| LOW | `SCREEN/*.png` | 900KB total | Blocked in `.claudeignore` |

---

## Files still too large (monitor these)

These are application code files that are legitimately large. Monitor them as the project grows.

| File | Size | Concern |
|---|---|---|
| `backend/app/scripts/process_article.py` | 23KB | One-shot script doing too much — candidate for service refactor |
| `frontend/app/(admin)/admin/articles/[id]/page.tsx` | 13KB | Complex article editor — may need component extraction |
| `backend/app/services/ai/localizer.py` | 10KB | Acceptable — core service |
| `backend/alembic/versions/20260503_*.py` | 10KB | Initial schema — will not grow |
| `backend/app/api/v1/articles.py` | 8KB | Growing API — watch for logic leaking into routes |
| `frontend/app/[locale]/articles/[slug]/page.tsx` | 8KB | Article detail — SEO + structured data makes it complex |

**Threshold**: Flag any file approaching 15KB for review. Files over 20KB in `services/` or `app/` layers are a signal of missing abstraction.

---

## Context architecture created

```
docs/ai-context/
├── active-tasks.md         # Session resume + handoff protocol
├── ai-pipeline.md          # AI localization, quality gate, prompt system
├── auth.md                 # Authentication, JWT, rate limiting
├── backend.md              # Backend stack, layers, conventions
├── context-loading-rules.md # What to load, when, hard limits
├── database.md             # Schema, migrations, conventions
├── deployment.md           # CI/CD, environments, rollback
├── final-report.md         # This file
├── frontend.md             # Next.js, RTL, RSC, SEO, TypeScript
├── infrastructure.md       # Services, costs, R2, Redis
├── product.md              # Mission, editorial workflow, metrics
├── roadmap.md              # What's built, what's pending, priorities
├── session-reset-strategy.md # When/how to reset, handoff protocol
└── task-routing.md         # Task type → which files to load
```

---

## Recommended daily workflow

### Starting a session

```
1. CLAUDE.md auto-loads (always)
2. Read docs/ai-context/active-tasks.md
3. Check task type → read task-routing.md for the right domain files
4. Load 1-2 domain files only
5. Read only the files you'll edit
```

### During a session

- Keep `/context` usage under 10% for a surgical task, under 30% for a feature build.
- If you accidentally read a large file, note it — consider a reset if context feels polluted.
- Domain files are ~700 tokens each — read as many as the task needs, but stop adding.

### Ending a session

```
1. Commit or stash all work
2. Update docs/ai-context/active-tasks.md
3. Log any new architecture decisions in docs/DECISIONS.md
4. Note exact next step for next session
```

### Weekly maintenance

- Check `docs/ai-context/active-tasks.md` — mark completed tasks, remove stale ones.
- Check `docs/ai-context/roadmap.md` — move completed items, update priorities.
- Review if any domain context file is stale (>2 weeks old with major changes to the domain).

---

## What was NOT changed

- No application code was modified.
- No service logic was touched.
- No database schema was altered.
- No frontend components were changed.
- `docs/DECISIONS.md` content was preserved.
- All prompt files are intact and unmodified.
- `backend/CLAUDE.md` does not exist — no action taken.
- `frontend/CLAUDE.md` (11B, points to AGENTS.md) — left as-is.
