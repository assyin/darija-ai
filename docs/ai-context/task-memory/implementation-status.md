# Implementation Status

> Update: when a feature or sub-feature changes state.
> Rule: more granular than roadmap.md. Capture sub-task level. No prose.
> Do NOT duplicate roadmap.md's high-level list — only track active/in-progress/blocked granularity here.

---

## Legend

`✅ done` · `🟡 in progress` · `🔲 not started` · `🚫 blocked`

---

## Backend

### REST API
| Sub-task | Status | Notes |
|---|---|---|
| Articles public endpoints (GET list, GET detail) | ✅ | `api/v1/articles.py` — committed `145d487` |
| Articles admin endpoints (PATCH, publish, unpublish, regenerate-image) | ✅ | Committed `145d487` |
| Settings endpoints (GET public, GET/PATCH admin, bulk) | ✅ | Committed `145d487` |
| Router wired in main.py | ✅ | Committed `145d487` |
| Auth middleware on admin routes | ✅ | `require_admin` on all 10 admin handlers — committed `d247de3` |
| Rate limiting on `/auth/token` | ✅ | 5 req/IP/10 min, Redis fixed-window — committed `49e7450` |
| Rate limiting on public routes | 🔲 | Not yet integrated |

### Auth
| Sub-task | Status | Notes |
|---|---|---|
| `core/security.py` — JWT validation + `require_admin` | ✅ | Committed `d247de3` |
| `api/v1/auth.py` — POST /auth/token | ✅ | Email + password → HS256 JWT, 1h — **production-ready MVP** |
| `core/rate_limit.py` — IP-based rate limiter | ✅ | 5/10min, fail-open — committed `49e7450` |
| `schemas/auth.py` — AdminUser, LoginRequest, TokenResponse | ✅ | Committed `d247de3` |
| Config: `admin_email`, `admin_password` (SecretStr) | ✅ | Dev defaults, prod guard in lifespan |
| Frontend login form → backend token | ✅ | NextAuth Credentials → `/auth/token`; JWT in httpOnly session (D2) — 2026-05-25 |
| Password hashing | 🔲 | Explicit MVP deferral |

### AI Pipeline
| Sub-task | Status | Notes |
|---|---|---|
| RSS scraping + dedup | ✅ | `rss_fetcher.py`, `ingestion.py` |
| Relevance filter | ✅ | `relevance_filter.py` |
| Haiku 4.5 localization | ✅ | `localizer.py` |
| Quality gate (6 checks) | ✅ | `quality_gate.py` |
| Prompt caching via Redis | ✅ | In `localizer.py` |
| Image gen (Flux Schnell + R2) | ✅ | `image_generator.py`, `r2_storage.py` |
| Cost logging to ai_logs table | ✅ | In `claude_client.py` |
| Sentry cost alert (>$5/day) | 🔲 | Sentry not yet integrated |

### Worker / Scheduling
| Sub-task | Status | Notes |
|---|---|---|
| One-shot pipeline script | ✅ | `app/scripts/process_article.py` (kept as manual wrapper) |
| `ArticleProcessor` service (per-article pipeline) | ✅ | `app/services/pipeline/article_processor.py` — manages `processing_status` transitions, mypy-strict clean |
| arq job queue wiring | ✅ | `app/workers/jobs/{fetch_articles,process_articles,retry_failed}.py` |
| arq scheduler (cron, no APScheduler — D1) | ✅ | `app/workers/settings.py` — boots 4 jobs + 3 cron, Redis-connected |
| Scheduled scraping (every 30min) | ✅ | cron `fetch_articles` minute={0,30}; process every 10min; retry hourly |
| `make worker` / `fetch-articles` / `process-pending` | ✅ | root `Makefile` + `app/scripts/process_pending.py` |
| Worker integration tests (5) | ✅ | `tests/integration/test_article_processor.py` — happy/rejected/failed/image-fail/not-found |

### Database
| Sub-task | Status | Notes |
|---|---|---|
| Initial schema (7 tables) | ✅ | Migration `20260503_1912_*` |
| site_settings table | ✅ | Migration committed `145d487` |
| Seed data (RSS sources) | ✅ | `seed_sources.py` |
| Seed site settings | ✅ | `seed_site_settings.py` committed `145d487` |

### Tests
| Sub-task | Status | Notes |
|---|---|---|
| Unit: quality_gate | ✅ | |
| Unit: bidi | ✅ | |
| Unit: r2_storage | ✅ | |
| Unit: replicate_client | ✅ | |
| Unit: security (8 tests) | ✅ | Committed `d247de3` |
| Integration: articles API | ✅ | Committed `145d487`, updated `d247de3` |
| Integration: settings API | ✅ | Committed `145d487`, updated `d247de3` |
| Integration: auth API (5 tests) | ✅ | Committed `49e7450` — covers 429 path, IP isolation, fail-open |
| Unit: localizer | 🔲 | |
| Unit: scraping | 🔲 | |
| Frontend: Vitest + Playwright | 🔲 | REFACTOR-05 |

### Distribution
| Sub-task | Status | Notes |
|---|---|---|
| LinkedIn posts | 🔲 | |
| Meta (Instagram) | 🔲 | |
| Newsletter (Resend) | 🔲 | |
| Social post DB logging | 🔲 | Model exists, service not built |

---

## Frontend

### Public site
| Sub-task | Status | Notes |
|---|---|---|
| Home page (article grid) | ✅ | `publicApi.getArticles(10)` — committed `86418b1`. E2E verified 2026-05-06. |
| Article list page | ✅ | `publicApi.getArticles(100)` — committed `86418b1`. E2E verified 2026-05-06. |
| Article detail page | ✅ | `publicApi.getArticle(slug)` + related fetch — committed `86418b1`. E2E verified 2026-05-06. |
| Locale routing (ar-MA) | ✅ | next-intl wired |
| RTL layout + Tajawal font | ✅ | Verified: 8–12 `dir="rtl"` attrs per page, `lang="ar-MA"` on root `<html>` |
| About / contact / services pages | ✅ | Static content |
| JSON-LD on article pages | ✅ | NewsArticle schema, bdi-stripped fields, body placement — E2E verified |
| `generateMetadata` on home/articles | 🔲 | FIX-S1 — pages use root default only |
| Custom `not-found.tsx` | 🔲 | FIX-M2 — built-in English 404 currently |
| OG image dimensions 1200×630 | 🔲 | FIX-M3 — currently 1024×576 |
| Sitemap / robots.txt / RSS feed | 🔲 | |
| Plausible / Vercel Analytics | 🔲 | |

### Admin panel
| Sub-task | Status | Notes |
|---|---|---|
| Articles list | ✅ | Wired via `adminApi` + authed proxy — 2026-05-25 |
| Article editor (markdown) | ✅ | Wired: view/edit/publish/unpublish/regenerate-image via proxy |
| Settings page | ✅ | Wired: list + bulk update via proxy |
| Sources management | 🟡 | Still hardcoded — **no backend `/admin/sources` endpoint exists** (out of P0-B scope) |
| Login page → `/api/v1/auth/token` | ✅ | NextAuth Credentials, real email+password (D2) |
| Real API integration (admin) | ✅ | Same-origin proxy `app/api/admin/[...path]` injects Bearer from session |

---

## Infrastructure
| Sub-task | Status | Notes |
|---|---|---|
| Local dev (Docker Compose) | ✅ | postgres + redis |
| CI/CD pipeline | 🔲 | `.github/workflows/` not created |
| Staging env (Railway) | 🔲 | |
| Sentry integration | 🔲 | SDK installed, DSN not set |
| Uptime Robot | 🔲 | |
| Doppler secrets (prod) | 🔲 | |

---

*Last updated: 2026-05-25 (P0-A Worker + Scheduler implemented — arq-only, 5 integration tests passing)*

> ⚠️ Known pre-existing test failure (unrelated to P0-A): `test_admin_list_articles_returns_existing` fails because the only seeded article (id=1) was published during E2E (2026-05-06), so the `is_published=false` draft filter returns empty. Data drift, not a code regression.
