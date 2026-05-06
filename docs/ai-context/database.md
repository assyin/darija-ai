# Database Context — DarijaAI

> Load this file when: schema changes, migrations, models, queries, DB conventions.

---

## Engine

PostgreSQL 16 on Neon (free tier, 3GB). Async driver: `asyncpg`. ORM: SQLModel (wraps SQLAlchemy 2.x). Migrations: Alembic.

## Tables (current schema)

| Table | File | Purpose |
|---|---|---|
| `sources` | `models/source.py` | RSS source configuration |
| `raw_articles` | `models/raw_article.py` | Scraped articles before processing |
| `articles` | `models/article.py` | Processed + published/draft articles |
| `darija_glossary` | `models/darija_glossary.py` | Canonical tech term translations |
| `ai_logs` | `models/ai_log.py` | Every Claude/AI call: tokens + cost |
| `site_settings` | `models/site_setting.py` | Admin-configurable site settings |
| `social_posts` | `models/social_post.py` | Social distribution log |
| `subscribers` | `models/subscriber.py` | Newsletter subscribers |

## Migration rules (sacred)

- **Never edit a migration merged to `main`.** Always create a new one.
- **Never `DROP COLUMN` directly.** Use the 5-PR expand/contract pattern.
- Filenames: `YYYYMMDD_HHMM_short_description.py`
- Every migration has both `upgrade()` and `downgrade()`.
- Create with: `cd backend && uv run alembic revision --autogenerate -m "short_description"`
- Apply with: `uv run alembic upgrade head`

## Schema conventions

- All tables: `id` (PK), `created_at` (TIMESTAMPTZ), `updated_at` where mutable.
- Timestamps: always `TIMESTAMPTZ` (UTC). Never naive datetimes.
- Money/cost: `DECIMAL(10, 6)` USD. Never float.
- Enums: `VARCHAR + CHECK constraint`, not Postgres native ENUMs.
- Soft deletes: `deleted_at TIMESTAMPTZ NULL`, not `is_deleted BOOLEAN`.
- All FKs: explicit `ON DELETE` (CASCADE / RESTRICT / SET NULL).
- Booleans: `is_*` or `has_*` prefix.

## Indexing rules

- Index every FK column.
- Index every column used in `WHERE` or `ORDER BY` on hot queries.
- Index name pattern: `idx_<table>_<columns>`.

## Query rules

- No `SELECT *` in production code.
- No N+1 queries — use `selectinload()` or joins on all list endpoints.
- No raw SQL except inside Alembic migrations.
- Connection pool: 5–20 connections per service.

## Current migrations

- `20260503_1912_a40f4ff284f0_create_initial_schema.py` — initial 7-table schema
- `20260505_0948_d49d139aee40_create_site_settings_table.py` — site_settings table

## Naming conventions

- Tables: `snake_case`, plural.
- Columns: `snake_case`.
- FKs: `<table>_id` (e.g., `source_id`).
- Indexes: `idx_<table>_<columns>`.
