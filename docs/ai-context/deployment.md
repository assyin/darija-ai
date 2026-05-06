# Deployment Context — DarijaAI

> Load this file when: CI/CD, environments, Railway, Vercel, releases, rollbacks.

---

## Environments

| Env | Backend | Frontend | Database | Trigger |
|---|---|---|---|---|
| Local | `localhost:8000` | `localhost:3000` | Docker Compose | Manual |
| Staging | Railway preview | Vercel preview | Neon branch | `staging` branch push |
| Production | Railway prod | Vercel prod | Neon prod | `main` branch push |

## Deployment method

**Frontend → Vercel**: Auto-deploys on push to `main`. Zero config needed.

**Backend → Railway**: Auto-deploys on push to `main` via `railway.json`.

**Migrations**: Run automatically as part of backend deploy. Applied with `alembic upgrade head`.

**Never auto-rollback migrations** — fix forward only.

## CI/CD pipeline (`.github/workflows/`)

**On every PR:**
1. Lint: `ruff check`, `eslint`
2. Type check: `mypy --strict`, `tsc --noEmit`
3. Tests: `pytest`, `vitest`
4. Build: `next build`, `docker build`

**On merge to `main`** (same as PR + ):
5. Deploy backend to Railway
6. Deploy frontend to Vercel
7. Run DB migrations
8. Smoke tests against staging
9. Notify Sentry of release

**Status**: CI/CD pipeline not yet wired. Deploys currently manual.

## Manual deploy commands

```bash
make deploy-backend    # Railway redeploy
make logs-backend      # Tail Railway logs
make logs-frontend     # Tail Vercel logs
```

## Rollback

- **Frontend**: Vercel instant rollback (1-click in dashboard).
- **Backend**: Railway → redeploy previous build.
- **Database**: No rollback. Fix forward with a new migration.

## Release tagging

```bash
git tag v1.2.3 && git push --tags
```

Semantic versioning. Changelog via `git-cliff` on tag.

## Makefile commands (all dev/deploy operations)

See `Makefile` at repo root. Key targets:
- `make dev` — backend + frontend concurrently
- `make db-migrate` — apply pending migrations
- `make db-revision msg="..."` — create new migration
- `make fetch-articles` — trigger manual scrape
- `make process-pending` — process pending articles
- `make check` — lint + typecheck + test (run before every commit)
