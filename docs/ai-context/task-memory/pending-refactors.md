# Pending Refactors

> Update: when new technical debt is identified, or when an item is resolved.
> Rule: only add items that genuinely impede future work. No cosmetic cleanup. Remove when done.

---

## Priority: HIGH (blocks future work)

### [REFACTOR-01] `process_article.py` → proper worker jobs
**File**: `backend/app/scripts/process_article.py` (23KB)
**Problem**: God script that orchestrates the entire pipeline (scrape → localize → image → save). Not testable as units. Cannot be scheduled or retried per-step.
**What it needs**: Extract into `app/workers/jobs/fetch_articles.py`, `process_articles.py`, `distribute.py`. Add `app/workers/scheduler.py` as APScheduler entrypoint.
**Blocked by**: Nothing. But should be done before adding scheduling.
**Effort**: ~1 session.

### [REFACTOR-02] Frontend uses mock data everywhere
**Files**: Most `frontend/app/[locale]/*.tsx` and `frontend/app/(admin)/admin/*.tsx`
**Problem**: Pages render hardcoded mock data instead of calling the backend API. Nothing is real end-to-end.
**What it needs**: Wire `frontend/lib/api.ts` client to backend, replace mock data with real fetch calls. Start with article list and article detail (highest value for SEO).
**Blocked by**: Backend API must be committed first (REFACTOR-01 not required, just the routes).
**Effort**: ~1-2 sessions.

---

## Priority: MEDIUM (fix before scaling)

### [REFACTOR-03] Auth not wired in admin routes
**Files**: `backend/app/api/v1/articles.py`, `backend/app/api/v1/settings.py`
**Problem**: Admin routes exist but JWT validation (`require_admin` dependency) is not applied. Admin panel is effectively open.
**What it needs**: Build `backend/app/core/security.py` from scratch (file does not exist). Implement HS256 JWT validation, `AdminUser` schema, and `require_admin` FastAPI dependency. Apply `user: AdminUser = Depends(require_admin)` to all admin router handlers. Wire NextAuth session in frontend.
**Blocked by**: Nothing — must be built from scratch, not wired up.
**Effort**: ~1 session.

### [REFACTOR-04] Sentry integration is installed but not configured
**Files**: `backend/app/main.py` (imports `sentry_sdk`), no DSN set
**Problem**: Error tracking, performance tracing, and cost alerts all depend on Sentry. None are active.
**What it needs**: Add `SENTRY_DSN` env var, call `sentry_sdk.init()` with FastAPI integration + performance tracing. Add daily cost alert.
**Effort**: ~2 hours.

### [REFACTOR-05] No frontend test suite
**Files**: `frontend/` — 0 test files
**Problem**: Article editor (13KB), article detail page (8KB), home page (6KB) — all untested. RTL rendering, API integration, admin publish flow.
**What it needs**: Vitest + Testing Library setup. 3 E2E paths with Playwright: home → article, admin login → publish, newsletter signup.
**Effort**: ~1 session.

---

## Priority: LOW (quality of life)

### [REFACTOR-06] Non-production AI code should be isolated or archived
**Files**: `cross_model_pipeline.py`, `openai_client.py`, `critic_editor.py`, `prompts/critic_v1.md`
**Problem**: Dead code in the active module path. Blocked in `.claudeignore` but still exists in the repo.
**Options**: Move to `app/services/ai/_experimental/`, or keep as-is and rely on `.claudeignore`.
**Decision needed**: Worth doing cleanly if/when re-evaluating multi-model approach.
**Effort**: ~30 min.

### [REFACTOR-07] `localizer_v1.md` prompt extended without a new version file
**File**: `backend/app/services/ai/prompts/localizer_v1.md`
**Problem**: The prompt was modified in-place (+107 lines, unstaged). Per project rules, deployed versions are immutable. Since this hasn't shipped to prod yet, it's acceptable now — but the moment it's in a prod commit, further changes must become `localizer_v2.md`.
**Action needed**: After committing, treat `localizer_v1.md` as frozen. Next change → `localizer_v2.md` + update `LOCALIZER_PROMPT_VERSION` config.
**Effort**: 0 (just discipline).

---

*Last updated: 2026-05-06*
