# Pending Refactors

> Update: when new technical debt is identified, or when an item is resolved.
> Rule: only add items that genuinely impede future work. No cosmetic cleanup. Remove when done.

---

## Priority: HIGH (blocks future work)

### [FIX-M2] No custom `not-found.tsx` — 404 page is English, unbranded
**Found**: E2E Phase 6 (2026-05-06)
**Files**: `frontend/app/[locale]/not-found.tsx` — does not exist
**Problem**: Next.js built-in 404 renders "This page could not be found." in English. `<html>` tag loses `lang="ar-MA"` and `dir="rtl"`. Wrong for a Moroccan Arabic platform.
**Fix**: Create `frontend/app/[locale]/not-found.tsx` with branded Darija content (404 heading, link back to home).
**Effort**: ~20 min.

### [FIX-M3] OG image dimensions 1024×576 — spec requires 1200×630
**Found**: E2E Phase 5 (2026-05-06)
**File**: `frontend/app/[locale]/articles/[slug]/page.tsx:42`
**Problem**: `generateMetadata` hardcodes `{ width: 1024, height: 576 }`. CLAUDE.md spec and Twitter/OG validators require 1200×630. Impacts social sharing previews.
**Fix**: Change to `width: 1200, height: 630`. Note: actual R2 images are generated at 1024×576 by `flux-schnell` — either update image generator output size OR keep metadata at actual dimensions and document the deviation.
**Effort**: ~10 min (metadata only) or ~30 min (if image generator also updated).

### [FIX-M1] Calendly `href=""` — CTA link self-navigates
**Found**: E2E Phase 5 (2026-05-06)
**File**: `backend/app/scripts/seed_site_settings.py` (`calendly_url` key), `cta_template_darija` template
**Problem**: `calendly_url` is empty string. `{{calendly_url}}` resolves to `""`. Markdown renders `[حجز call مجاني]()` → `<a href="">` → clicking navigates to current page.
**Fix option A**: Set real Calendly URL in `site_settings` via admin API.
**Fix option B**: Remove Calendly line from `cta_template_darija` until URL is ready.
**Effort**: ~5 min (data change only, no code change).



### [REFACTOR-01] ✅ RESOLVED (2026-05-25) — `process_article.py` → worker jobs
**Done**: Per-article pipeline extracted into `app/services/pipeline/article_processor.py` (testable, manages `processing_status`). arq jobs in `app/workers/jobs/` + `WorkerSettings` cron scheduler (D1: arq-only). `process_article.py` kept as manual one-shot wrapper. 5 integration tests passing.

### [REFACTOR-02] Phase B — Admin panel API wiring
**Files**: `frontend/app/(admin)/admin/*.tsx`
**Problem**: Admin pages (articles list, article editor, settings, sources) use mock data. Login page not wired to `/api/v1/auth/token`.
**What it needs**: Wire admin pages with `Authorization: Bearer` token from login flow. Decide token storage (cookie vs localStorage).
**Blocked by**: Token storage decision (cookie vs localStorage) — see `recent-decisions.md`.
**Phase A**: ✅ Complete — committed `86418b1`.
**Effort**: ~1 session.

---

## Priority: MEDIUM (fix before scaling)

### [FIX-S1] Missing `generateMetadata` on home `/` and `/articles`
**Found**: E2E Phase 3/4 (2026-05-06)
**Files**: `frontend/app/[locale]/page.tsx`, `frontend/app/[locale]/articles/page.tsx`
**Problem**: Both pages fall back to root layout default `<title>DarijaAI</title>` with no OG tags. CLAUDE.md requires every route to export `generateMetadata()`.
**Fix**: Add `generateMetadata` to both pages using `getSiteSettings()` for `seo_default_title`, `seo_default_description`, and an OG image from R2.
**Effort**: ~30 min.

### [FIX-S5] `request_id` missing from backend 404 error body
**Found**: E2E Phase 2.4 (2026-05-06)
**File**: `backend/app/core/exceptions.py`
**Problem**: Error shape `{error:{code,message,details}}` — missing `request_id`. CLAUDE.md spec requires `{error:{code,message,request_id}}`. Frontend unaffected (only checks status code), but API clients and debuggability suffer.
**Fix**: Add `request_id` field to `NotFoundError` (and other error types) exception handler. Inject from request context via middleware.
**Effort**: ~30 min.

### [FIX-S4] Arabic plural grammar — "1 مقالات" should be "1 مقال"
**Found**: E2E Phase 4 (2026-05-06)
**File**: `frontend/messages/ar-MA.json` — `articles_list.count: "{count} مقالات"`
**Problem**: Template has no plural variant. `next-intl` supports ICU format: `{count, plural, one {مقال} few {مقالات} other {مقالات}}`.
**Fix**: Update translation key with ICU plural. Repeat for `fr.json` and `ar.json`.
**Effort**: ~15 min.

### [FIX-S2] `dateModified` equals `datePublished` in JSON-LD
**Found**: E2E Phase 5 (2026-05-06)
**File**: `frontend/app/[locale]/articles/[slug]/page.tsx:86`
**Problem**: `dateModified: article.published_at` — article edits don't update this field. Should use `article.updated_at`.
**Fix**: Change to `dateModified: article.updated_at ?? article.published_at`. Requires adding `updated_at` to `ArticlePublicDetail` schema (currently not exposed in public API).
**Effort**: ~20 min (backend schema + frontend).



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

### [REFACTOR-07] `localizer_v1.md` is now frozen — next change requires v2
**File**: `backend/app/services/ai/prompts/localizer_v1.md`
**Status**: Committed (`145d487`). Per project rules, any further changes must be `localizer_v2.md` + update `LOCALIZER_PROMPT_VERSION` config.
**Action needed**: Discipline only — no code change required until next prompt iteration.
**Effort**: 0 (awareness only).

---

*Last updated: 2026-05-06 (REFACTOR-02 Phase A removed — completed)*
