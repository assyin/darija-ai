# Active Tasks — DarijaAI

> This file tracks current work in progress. Update it at the end of each session.
> Load this file at the start of every session to resume context quickly.

---

## Currently in progress

### Next up: P1-C quick fixes + P0-C CI/CD
**Goal**: P1-C fast wins (FIX-M1/M2/M3, FIX-S1/S4/S5, password hashing, public rate limit), then P0-C (CI/CD + cloud envs).
**Status**: Not started.
**Context files**: `PROD-IMPLEMENTATION-PLAN.md` (P1-C / P0-C), `task-memory/pending-refactors.md`

---

## Recently completed

### P0-B — Admin panel API wiring (2026-05-25) · not yet committed
- **D2 resolved**: NextAuth Credentials → backend `/auth/token`; backend JWT in httpOnly session; same-origin authed proxy `app/api/admin/[...path]` injects Bearer server-side.
- `lib/auth.ts` (real credentials, dev-bypass removed), `types/next-auth.d.ts`, `login/page.tsx` (email+password form), `lib/api-client.ts` (`adminApi` same-origin client), proxy route handler.
- Admin pages (articles list, editor, settings) wired via `adminApi`. Fixed a pre-existing setState-in-effect eslint error in the editor.
- Verified E2E via curl: login→302+httpOnly cookie→proxy returns real data; publish/unpublish work; unauth → 401. tsc + eslint clean.
- Gap: sources page still hardcoded (no backend `/admin/sources` endpoint).

### P0-A — Worker + Scheduler (2026-05-25) · not yet committed
- **D1 resolved**: arq only (queue + native cron), no APScheduler.
- `services/pipeline/article_processor.py`: extracted per-article pipeline (localize → quality gate → image → persist draft); manages `raw_article.processing_status` (pending→processing→translated|rejected|failed). mypy-strict clean via `sqlmodel.col()`.
- `workers/jobs/{fetch_articles,process_articles,retry_failed}.py` + `workers/settings.py` `WorkerSettings`: 4 jobs + 3 cron (fetch/30min, process/10min, retry/hourly). Worker boots + connects to Redis (verified).
- `Makefile` (was missing): `worker`, `fetch-articles`, `process-pending` + `process_pending.py` manual script.
- 5 integration tests (`test_article_processor.py`) on real Postgres — all passing. Full suite: 56 pass, 1 pre-existing unrelated failure (`test_admin_list_articles_returns_existing` — data drift).

### E2E Product Verification — Full public stack (2026-05-06) · no commits (verification only)
- **Phase 0**: Docker healthy (postgres + redis). Backend started via `.venv/Scripts/uvicorn.exe`. Frontend via `pnpm dev`.
- **Phase 1 (DB)**: 1 published article (`salesforce-slackbot-ai-agent-workplace-2026`), 18 site settings seeded. All required fields populated.
- **Phase 2 (API)**: All 5 endpoints pass. Shapes match `ArticlePublic` / `ArticlePublicDetail` TypeScript types exactly. One spec gap: `request_id` missing from 404 error body (see FIX-S5).
- **Phase 3 (home `/`)**: All checks pass. RTL intact, article card renders correctly, all 4 CTA service pills present, no hydration errors.
- **Phase 4 (`/articles`)**: All checks pass. Count string has Arabic plural grammar issue (see FIX-S4).
- **Phase 5 (`/articles/<slug>`)**: All checks pass. `stripBdi()` confirmed working in all metadata. JSON-LD valid. Calendly `href=""` (see FIX-M1). OG dims 1024×576 (see FIX-M3). No hydration errors.
- **Phase 6 (404)**: HTTP 404 confirmed. Next.js `notFound()` triggered correctly. No custom 404 page (see FIX-M2).
- **Verdict**: MVP-demo-ready. No blockers. Three medium fixes before public launch.

### REFACTOR-02 Phase A — Frontend public API integration (2026-05-06) · commit `86418b1`
- `frontend/lib/api-client.ts`: removed default `cache: "no-store"` (unblocks ISR); added private `REVALIDATE_ARTICLES` (`satisfies RequestInit`); added `publicApi.getArticles(limit)` using `URLSearchParams` and `publicApi.getArticle(slug)` with 404-only swallow
- `frontend/app/[locale]/page.tsx`, `articles/page.tsx`, `articles/[slug]/page.tsx`: removed 3 duplicated `API_BASE` constants and 5 local fetch functions; all three pages now use `publicApi` helpers
- Net: -67 lines, +33 lines across 4 files. `pnpm tsc --noEmit` + `pnpm build` clean.

### REFACTOR-03b — IP rate limiting on admin login (2026-05-06) · commit `49e7450`
- `core/rate_limit.py`: `check_rate_limit()` — fixed-window counter, Redis INCR + EXPIRE NX pipeline
- `api/v1/auth.py`: direct `await check_rate_limit()` call before credential check; `_extract_ip()` reads `X-Forwarded-For[0]`
- Config: `auth_login_rate_limit_max_requests=5`, `auth_login_rate_limit_window_seconds=600`
- Fail-open on `RedisError` (logs warning, allows request through)
- 5 integration tests: success, wrong creds, 429 path, IP isolation, Redis fail-open — all passing
- Auth/security layer is now **production-ready for MVP**

### REFACTOR-03 — JWT admin auth (2026-05-06) · commit `d247de3`
- Built `core/security.py`: `create_access_token` + `require_admin` FastAPI dependency
- Built `api/v1/auth.py`: `POST /api/v1/auth/token` (email + password → HS256 JWT)
- Protected all 10 admin routes in `articles.py` and `settings.py`
- 8 unit tests for security.py (100% coverage)
- Integration tests updated with `auth_headers` fixture + 401 negative tests

### Repository stabilization (2026-05-06) · commits `145d487`, `fe10508`
- 36 unit tests passing
- Backend API committed: REST routes, schemas, site_settings, integration tests
- Frontend skeleton committed: Next.js 15 RTL public site + admin panel

### Context architecture refactor (2026-05-06) · commit `5846c89`
- CLAUDE.md reduced from ~17K to ~2.9K tokens
- Modular docs/ai-context/ domain files created
- Task memory system created under docs/ai-context/task-memory/

### AI Localization Pipeline (2026-05-04) · commit `1d37ec3`
- Haiku 4.5 single-pass production mode (ADR-002)

---

## Blocked / Pending

| Task | Blocker |
|---|---|
| Worker / APScheduler (REFACTOR-01) | Design decision: arq vs direct APScheduler |
| REFACTOR-02 Phase B (admin wiring) | Token storage decision (cookie vs localStorage) |
| NextAuth magic link | Need Resend API key + magic link template |
| CI/CD pipeline | Need GitHub repo secrets configured |
| Staging env | Need Railway staging service created |

---

## Session handoff notes

**Last session**: E2E verification complete (Phases 0–6). No code changes — verification only. 3 medium issues + 5 spec gaps documented.
**Commits this session**: None.
**Next session**: Fix FIX-M2 (custom 404), FIX-M3 (OG dims), FIX-M1 (Calendly), then REFACTOR-02 Phase B (admin wiring — needs token storage decision first).
**Pre-session requirement**: Docker running. Backend + frontend running (backend: `.venv/Scripts/uvicorn.exe app.main:app --reload` from `backend/`). Services were left running at session end.

---

> **Protocol**: When ending a session, update this file before closing. Include:
> - What was completed
> - What's next
> - Any new decisions (log in `docs/DECISIONS.md`)
> - Files modified this session
