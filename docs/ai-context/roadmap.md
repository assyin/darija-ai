# Roadmap & Current State — DarijaAI

> Load this file when: planning new features, scoping work, checking what's built vs. pending.

---

## What's built (as of 2026-05-06)

### Backend
- [x] Database schema — 8 tables, 2 Alembic migrations
- [x] RSS scraping pipeline — `rss_fetcher.py`, `ingestion.py`, `relevance_filter.py`
- [x] AI localization — `localizer.py` with Haiku 4.5, caching, cost logging
- [x] Quality gate — 6-check validation before draft creation
- [x] Image generation — Replicate Flux Schnell + R2 upload
- [x] One-shot pipeline script — `app/scripts/process_article.py`
- [x] REST API — articles CRUD + site settings (`/api/v1/articles`, `/api/v1/settings`)
- [x] Unit tests — quality_gate, bidi, r2_storage, replicate_client
- [x] Integration tests — articles API, settings API

### Frontend
- [x] Next.js 15 App Router skeleton with next-intl (Arabic locale)
- [x] Public site — home (article grid), article detail page, about/contact/services
- [x] Admin panel — articles list, article editor (markdown), settings, sources, login page
- [x] RTL layout with Tajawal font and tailwindcss-rtl
- [x] shadcn/ui component library (copy-pasted)
- [x] Public article card, header, footer, newsletter signup, contact form

## What's NOT yet built

### Backend
- [ ] APScheduler worker (`app/workers/`) — pipeline currently triggered manually
- [ ] `arq` job queue wiring — background processing queue
- [ ] Distribution services — LinkedIn, Meta (Instagram), newsletter
- [ ] Full article processing triggered from API (end-to-end automated)
- [ ] Admin JWT auth middleware fully wired
- [ ] Sentry integration
- [ ] `structlog` production logging configured

### Frontend
- [ ] NextAuth magic link login fully wired (scaffolded, not connected)
- [ ] Frontend test suite (Vitest + Testing Library)
- [ ] Real API integration (currently using mock/static data in many pages)
- [ ] Sitemap, robots.txt, RSS feed route
- [ ] Newsletter backend integration
- [ ] Plausible / Vercel Analytics integration
- [ ] JSON-LD schema on article pages

### Infrastructure
- [ ] CI/CD pipeline (`.github/workflows/`)
- [ ] Staging environment on Railway
- [ ] Doppler secrets setup for prod
- [ ] Uptime Robot monitoring
- [ ] Sentry project setup

## Priority order (recommended next)

1. Worker/scheduler + arq queue → makes pipeline automated
2. Auth wiring → enables secure admin panel
3. Frontend ↔ API real integration → end-to-end article flow
4. CI/CD pipeline → enables safe deploys
5. Distribution → LinkedIn/newsletter post-publish
