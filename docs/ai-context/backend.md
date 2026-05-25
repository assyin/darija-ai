# Backend Context — DarijaAI

> Load this file when: API routes, services, models, schemas, workers, Python code.

---

## Stack

- Python 3.12 · FastAPI ≥0.115 · SQLModel · asyncpg · Alembic
- `uv` for package management (NOT pip, NOT poetry)
- `arq` for job queue (NOT Celery) · Redis via Upstash
- `httpx` async HTTP · `structlog` logging · `ruff` lint/format · `mypy --strict`
- Scraping: `feedparser` + `selectolax` (not BeautifulSoup)

## Layer rules (strictly enforced)

| Layer | Location | Rule |
|---|---|---|
| Routes | `app/api/v1/` | Thin controllers: validation + delegation only. Zero business logic. |
| Business logic | `app/services/` | All logic lives here. Framework-agnostic. |
| DB tables | `app/models/` | SQLModel table definitions. Never expose directly via API. |
| API contracts | `app/schemas/` | Pydantic I/O models. Always use these in responses. |
| Scripts | `app/scripts/` | One-shot CLI operations. Not HTTP-triggered. |
| Config | `app/core/config.py` | Pydantic Settings. No config in code. |

## Actual service structure (current state)

```
app/services/
├── scraping/       ingestion.py, rss_fetcher.py, relevance_filter.py
├── ai/             localizer.py, claude_client.py, quality_gate.py
│   └── prompts/    localizer_v1.md  (+ non-prod: critic*, rewriter*, cross_model*)
├── images/         image_generator.py, replicate_client.py, r2_storage.py
└── (distribution/ not yet built)
```

**Note**: Worker/scheduler (`app/workers/`) not yet built. One-shot pipeline runs via `app/scripts/process_article.py`.

## Async rules

- All I/O is async (`async def`, `await`). Never sync I/O in async functions.
- `asyncio.gather()` for parallel independent calls. Never `await` in a loop.
- Long-running work → background jobs, not API handlers.

## Type rules

- Every function has full type hints. Modern unions: `X | None` not `Optional[X]`.
- No `dict[str, Any]` as pseudo-objects — use Pydantic/dataclasses.
- `mypy --strict` must pass. No `type: ignore` without a comment explaining why.

## Error handling

Custom hierarchy in `app/core/exceptions.py`:
`AppError → NotFoundError | ValidationError | ExternalServiceError | AIQualityError`

Single global exception handler maps to HTTP status. Never catch `Exception` without re-raising or logging with full context. External calls: tenacity retry + timeout + Sentry breadcrumb.

## Logging

`structlog` only. Key=value structured fields:
```python
logger.info("article.localized", article_id=42, duration_ms=120, tokens_used=890)
```
Never f-string logs. Every external API call: log start + end + duration + cost.

## API conventions

- Prefix: `/api/v1/`. Breaking changes → `/v2`.
- Cursor-based pagination. Lists return `{ "data": [...], "next_cursor": "...", "has_more": true }`.
- Error shape: `{ "error": { "code": "SCREAMING_SNAKE", "message": "...", "request_id": "..." } }`.
- Dates: ISO 8601 with timezone `2026-05-06T14:30:00Z`.

## Current API endpoints

- `GET/POST /api/v1/articles` — article list + creation
- `GET/PATCH /api/v1/articles/{id}` — article detail + update
- `GET/PATCH /api/v1/settings` — site settings

## Testing

- `pytest` + `pytest-asyncio` + `httpx`
- 80%+ coverage target on `services/`
- Mock external APIs with `respx`. Real Postgres + Redis in integration tests.
- Test through public service interface only — no private method testing.
