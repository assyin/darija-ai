# Current Focus

> Update: every session start and end. This is the first file to load.
> Rule: only ONE active focus at a time. Everything else goes to implementation-status.md.

---

## Active task

**Wiring the REST API and making the full backend pipeline testable end-to-end.**

Started: 2026-05-06 (unstaged, not yet committed)

## Files actively modified (unstaged)

| File | Change |
|---|---|
| `backend/app/main.py` | Added 4 router includes (articles public/admin, settings public/admin) |
| `backend/app/models/__init__.py` | Exports updated (site_setting added) |
| `backend/app/services/ai/prompts/localizer_v1.md` | Extended (+107 lines — prompt refinement) |
| `backend/pyproject.toml` | Added pytest asyncio session scope |

## Untracked files pending first commit

- `backend/app/api/v1/articles.py` + `settings.py` — REST endpoints
- `backend/app/schemas/article.py` + `site_setting.py` — API contracts
- `backend/app/models/site_setting.py` — new DB model
- `backend/alembic/versions/20260505_*.py` — site_settings migration
- `backend/tests/integration/` — 2 integration test files + conftest
- `backend/app/scripts/seed_site_settings.py`
- `frontend/` — full frontend implementation (new structure)

## Next concrete action

1. Run `cd backend && uv run pytest tests/integration/ -v` → verify tests pass
2. Commit backend changes: API routes, schemas, site_setting model, migration, tests
3. Commit frontend separately

## Blocked on

Nothing currently blocking. Frontend-to-backend real API integration is the next milestone after this commit.

---

*Last updated: 2026-05-06*
