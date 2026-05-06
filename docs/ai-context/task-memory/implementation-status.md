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
| Articles public endpoints (GET list, GET detail) | 🟡 | Code written, not committed |
| Articles admin endpoints (POST, PATCH, DELETE) | 🟡 | Code written, not committed |
| Settings endpoints (GET, PATCH) | 🟡 | Code written, not committed |
| Router wired in main.py | 🟡 | Diff applied, not committed |
| Auth middleware on admin routes | 🔲 | JWT validation not wired |
| Rate limiting on public routes | 🔲 | Upstash Ratelimit not integrated |

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
| One-shot pipeline script | ✅ | `app/scripts/process_article.py` (23KB) |
| APScheduler setup | 🔲 | No `app/workers/` directory yet |
| arq job queue wiring | 🔲 | arq installed, not wired |
| Scheduled scraping (every 30min) | 🔲 | Depends on APScheduler |

### Database
| Sub-task | Status | Notes |
|---|---|---|
| Initial schema (7 tables) | ✅ | Migration `20260503_1912_*` |
| site_settings table | 🟡 | Migration written, not committed |
| Seed data (RSS sources) | ✅ | `seed_sources.py` |
| Seed site settings | 🟡 | `seed_site_settings.py`, not committed |

### Tests
| Sub-task | Status | Notes |
|---|---|---|
| Unit: quality_gate | ✅ | |
| Unit: bidi | ✅ | |
| Unit: r2_storage | ✅ | |
| Unit: replicate_client | ✅ | |
| Integration: articles API | 🟡 | Written, not committed |
| Integration: settings API | 🟡 | Written, not committed |
| Unit: localizer | 🔲 | |
| Unit: scraping | 🔲 | |

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
| Home page (article grid) | 🟡 | Scaffolded, mock data |
| Article detail page | 🟡 | Scaffolded, mock data |
| Locale routing (ar-MA) | ✅ | next-intl wired |
| RTL layout + Tajawal font | ✅ | |
| About / contact / services pages | ✅ | Static content |
| Real API integration | 🔲 | Depends on backend commit |
| Sitemap / robots.txt / RSS feed | 🔲 | |
| JSON-LD on article pages | 🔲 | |
| Plausible / Vercel Analytics | 🔲 | |

### Admin panel
| Sub-task | Status | Notes |
|---|---|---|
| Articles list | 🟡 | Scaffolded, mock data |
| Article editor (markdown) | 🟡 | Scaffolded, 13KB |
| Settings page | 🟡 | Scaffolded, mock data |
| Sources management | 🟡 | Scaffolded |
| Login page (magic link) | 🟡 | UI done, NextAuth not wired |
| Real API integration (admin) | 🔲 | Depends on auth + backend commit |

---

## Infrastructure
| Sub-task | Status | Notes |
|---|---|---|
| Local dev (Docker Compose) | ✅ | postgres + redis |
| CI/CD pipeline | 🔲 | `.github/workflows/` not created |
| Staging env (Railway) | 🔲 | |
| Sentry integration | 🔲 | SDK installed, not configured |
| Uptime Robot | 🔲 | |
| Doppler secrets (prod) | 🔲 | |

---

*Last updated: 2026-05-06*
