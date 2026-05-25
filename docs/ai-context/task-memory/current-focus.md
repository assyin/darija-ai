# Current Focus

> Update: every session start and end. This is the first file to load.
> Rule: only ONE active focus at a time. Everything else goes to implementation-status.md.

---

## Active task

**P0-A (worker), P0-B (admin), P1-C (quick fixes) all DONE (2026-05-25). Next: P0-C CI/CD + cloud envs.**

Committed:
- `3da42a5` P0-A worker — branch `feat/worker-scheduler`
- `71a9f79` P0-B admin wiring — branch `feat/admin-wiring`
- P1-C quick fixes — branch `feat/prelaunch-fixes` (this commit)

P1-C done: FIX-M1 (CTA empty-link filter), FIX-M2 (branded Darija 404 ×2), FIX-M3 (OG 1200×630), FIX-S1 (generateMetadata home/articles), FIX-S4 (Arabic plural), FIX-S5 (request_id in errors), public rate limiting (60/min/IP). All verified live via curl. Password hashing intentionally skipped (deferred per decision log).

## Next concrete action

1. **P0-C** — CI/CD (GitHub Actions) + provision Railway/Vercel/Neon/Upstash/R2 + staging. Needs owner cloud access + secrets.
2. Smaller remaining items: FIX-S2 (dateModified=updated_at — needs backend to expose `updated_at` in ArticlePublicDetail), backend `/admin/sources` endpoint (to un-hardcode the admin sources page), frontend test suite (REFACTOR-05), SEO sitemap/robots/feed (P1-A), Sentry DSN (P1-B).

## Blocked on

- P0-C needs cloud account/secrets access (Railway, Vercel, Neon, Upstash, R2, GitHub secrets).

## Known pre-existing issue (not a regression)

`test_admin_list_articles_returns_existing` fails: the only seeded article (id=1) is published, so the `is_published=false` draft filter returns empty. Data drift since E2E publish. Full suite otherwise: 56 passed.

---

*Last updated: 2026-05-25*
