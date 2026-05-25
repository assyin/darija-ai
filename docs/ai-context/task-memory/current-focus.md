# Current Focus

> Update: every session start and end. This is the first file to load.
> Rule: only ONE active focus at a time. Everything else goes to implementation-status.md.

---

## Active task

**P0-A/B + P1-C + P0-C deployment scaffolding all DONE (2026-05-25). Next: owner provisions the Hetzner host.**

Committed branches (stacked on `main`):
- `feat/worker-scheduler` `3da42a5` — arq worker + cron
- `feat/admin-wiring` `71a9f79` — admin panel wired (NextAuth httpOnly + proxy)
- `feat/prelaunch-fixes` `55a4c83` — 404/SEO/request_id/rate-limit
- `feat/deploy-hetzner` (this commit) — **deployment: Hetzner all-in-one + R2**

**Deploy decision**: dropped Railway/Vercel/Neon/Upstash → single Hetzner box, Docker Compose + Caddy (auto-TLS), images via GHCR, Cloudflare R2 kept for images.

Built + verified: backend & frontend prod Dockerfiles (both `docker build` OK), `infra/docker-compose.prod.yml` (config valid, 6 services), `infra/Caddyfile` (valid), `.env.prod.example`, Postgres backup script, CI + Deploy GitHub workflows, `docs/DEPLOY.md`.

## Next concrete action (owner)

1. Create Hetzner CX22+ (Ubuntu 24.04), point DNS A record at it.
2. Install Docker, clone repo to `/opt/darija-ai`, `cp infra/.env.prod.example .env` and fill secrets.
3. Set GitHub repo: var `DOMAIN`; secrets `SSH_HOST`/`SSH_USER`/`SSH_KEY`.
4. First deploy + migrate + seed (see `docs/DEPLOY.md` §3). Then pushes to `main` auto-deploy.

## Remaining (smaller, optional)

FIX-S2 (expose `updated_at`), backend `/admin/sources` endpoint (un-hardcode admin sources page), frontend test suite (REFACTOR-05), SEO sitemap/robots/feed (P1-A), Sentry DSN (P1-B), Uptime Robot.

## Blocked on

- First deploy needs owner's Hetzner host + DNS + secrets (can't be done from here).

---

*Last updated: 2026-05-25*
