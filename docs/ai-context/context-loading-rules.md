# Context Loading Rules — DarijaAI

> Hard rules for what to load, when, and how much. Follow these to prevent context rot and token waste.

---

## Rule 1 — Start minimal, expand on demand

Begin every session with `CLAUDE.md` (auto-loaded) + `active-tasks.md` only.
Add domain files only when you need them. Stop when you have enough to proceed.

**Wrong**: Load all domain files at session start "just in case."
**Right**: Load `backend.md` when writing backend code. Load `frontend.md` when writing UI code.

---

## Rule 2 — Never load these files (blocked by `.claudeignore`)

These are auto-excluded. Do not manually read them unless directly editing the file itself.

| File / Pattern | Why |
|---|---|
| `backend/logs/*.log` | Runtime logs — ephemeral, 100–600KB |
| `backend/logs/*.md` | Model output test runs — historical artifacts |
| `SCREEN/*.png` | Screenshots — binary media |
| `docs/test-results/` | 50KB+ raw model comparison outputs |
| `claude.full.backup.md` | 41KB archived context — use `CLAUDE.md` instead |
| `backend/uv.lock` | 167KB lockfile — zero AI value |
| `frontend/pnpm-lock.yaml` | 227KB lockfile — zero AI value |
| `frontend/tsconfig.tsbuildinfo` | 266KB compiled cache |
| `backend/app/services/ai/prompts/localizer_v1.md` | 52KB — load only when editing the prompt |

---

## Rule 3 — Load on-demand only (not at session start)

These are small enough to load but only relevant in specific situations:

| File | Load when |
|---|---|
| `docs/DECISIONS.md` | Making or reviewing architecture decisions |
| `backend/alembic/versions/*.py` | Reviewing or creating migrations |
| `backend/app/services/ai/prompts/localizer_v1.md` | Directly editing the localizer prompt |
| `frontend/globals.css` | Working on global styles or design tokens |
| `backend/app/scripts/process_article.py` | Debugging or modifying the one-shot pipeline |
| `backend/app/services/ai/cross_model_pipeline.py` | Explicitly re-evaluating multi-model approach |

---

## Rule 4 — Maximum active files

Keep ≤10 files open in active context at once. When reading a new file, consider whether an older one can be dropped.

Prioritize:
1. Files you will edit this session
2. Domain context files for the current task
3. `CLAUDE.md` (always)

Deprioritize:
- Files from a completed sub-task
- Files read for orientation that are no longer needed

---

## Rule 5 — Lockfiles and generated files are never context

Never read: `uv.lock`, `pnpm-lock.yaml`, `tsconfig.tsbuildinfo`, `*.pyc`, `.next/`, `__pycache__/`, `node_modules/`.

If you need to know what's installed: read `backend/pyproject.toml` or `frontend/package.json`.

---

## Rule 6 — Large source files require justification

Files >10KB should only be loaded if you're actively modifying them:

| File | Size | Load only when |
|---|---|---|
| `backend/app/scripts/process_article.py` | 23KB | Modifying the pipeline script |
| `backend/app/services/ai/cross_model_pipeline.py` | 14KB | Re-evaluating multi-model approach |
| `frontend/app/(admin)/admin/articles/[id]/page.tsx` | 13KB | Editing the article editor |
| `backend/alembic/versions/20260503_*.py` | 10KB | Reviewing initial schema |

---

## Rule 7 — Prompt files are not AI context

The files in `backend/app/services/ai/prompts/` are **system prompts for the product's AI**, not documentation for Claude Code. Do not load them for context. Load them only when editing prompt content.

---

## Enforcement

`.claudeignore` at repo root enforces rules 2, 5, and parts of rule 7 automatically.
Rules 1, 3, 4, 6 require discipline — they are judgment calls, not enforced by tooling.
