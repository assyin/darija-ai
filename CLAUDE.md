# CLAUDE.md — DarijaAI

> Read fully before any code change. This overrides all defaults.
> **Context system**: Load `docs/ai-context/active-tasks.md` first, then route via `docs/ai-context/task-routing.md`.
> Full original: `claude.full.backup.md` · Frontend rules: `frontend/CLAUDE.md`

---

## 1. PROJECT RULES

**What this is**: Editorial AI/tech news platform in Moroccan Darija. NOT a translation service — content is localized editorially.

**Human review is mandatory**: All AI output is saved as draft (`is_published=False`). Owner reviews and approves in admin panel before publication. Never auto-publish.

**Budget constraint**: $50/mo infra cap. Always cache AI calls by content hash before making new ones.

**Darija content is sacred**: Never auto-edit Darija strings. The system prompt produces them; the owner validates them.

---

## 2. TECH STACK (locked — ask before adding or changing anything)

| Layer | Tools |
|---|---|
| Backend | Python 3.12+, FastAPI ≥0.115, SQLModel, asyncpg, Alembic, `uv` (not pip/poetry) |
| Queue | `arq` (not Celery), Redis via Upstash |
| HTTP | `httpx` async (not `requests`) |
| Quality | `ruff` (lint+format), `mypy --strict`, `pytest` + `pytest-asyncio` |
| Frontend | Next.js 15 App Router, TypeScript strict, Tailwind v4 + `tailwindcss-rtl`, `pnpm` (not npm/yarn) |
| UI | shadcn/ui (copy-paste, not a dep), `lucide-react`, `react-hook-form` + `zod` |
| AI | `claude-haiku-4-5` default · `claude-sonnet-4-6` opt-in · `flux-schnell` images |
| Infra | Vercel (frontend) · Railway (backend) · Neon (Postgres) · Cloudflare R2 (images) |

---

## 3. BACKEND CODING RULES

**Async**: Default to async for all I/O. Use `asyncio.gather()` for parallel calls — never `await` in a loop when calls are independent.

**Types**: Type hints on every function. Modern union syntax only: `X | None`, not `Optional[X]`. Pydantic/dataclasses for structured data, never `dict[str, Any]` as pseudo-objects.

**Layers** (strictly enforced):
- `api/` — thin controllers: validation + delegation only. Zero business logic, zero DB calls.
- `services/` — all business logic. Framework-agnostic. This is where the meat lives.
- `models/` = DB tables. `schemas/` = API contracts. Never expose ORM objects via API responses.
- `workers/` — call services only. No logic in workers.
- `utils/` — stateless pure functions only. State or I/O → it's a service.

**Errors**: Custom hierarchy in `core/exceptions.py`. Never catch `Exception` without re-raising or logging with full context. Wrap external API calls with tenacity retry + timeout.

**Logging**: Structured via `structlog`. Always key=value fields, never f-strings: `logger.info("event", article_id=42, duration_ms=120)`.

---

## 4. FRONTEND CODING RULES

**TypeScript**: `strict: true`, `noUncheckedIndexedAccess`. NO `any`, NO `as` casts without a comment, NO `!` assertions in production code. Discriminated unions over optional fields for state.

**RSC default**: Server Components by default. Mark `"use client"` only for state/effects/browser APIs/event handlers. Fetch data in RSC, pass down as props. No client-side fetching for SEO-critical content.

**RTL (non-negotiable)**:
- `<html lang="ar-MA" dir="rtl">` in root layout — never changes.
- Logical CSS properties: `ms-4` not `ml-4`. Plugin `tailwindcss-rtl` is mandatory.
- Font: Tajawal via `next/font/google`, preloaded. Arabic punctuation: `،` `؟`.
- Mixed Arabic/Latin content may need `<bdi>` tags.

**SEO**: Every route exports `generateMetadata()`. OG image required (1200×630 from R2). Canonical URL set. `NewsArticle` JSON-LD on article pages.

**Performance**: LCP < 2.0s mobile · CLS < 0.05 · JS bundle < 100kb gzipped/page · All images via `next/image` with explicit dimensions.

---

## 5. AI PIPELINE RULES

**Prompts are code**: Live in `backend/app/services/ai/prompts/*.md`. Never inline prompts as f-strings. Deployed versions are immutable — changes require a new versioned file (`localizer_v2.md`).

**ADR-002 (production decision)**: `claude-haiku-4-5` single-pass for all articles. Pass `model="claude-sonnet-4-6"` to Localizer for flagship pieces only. Cross-model pipeline code preserved but not in production.

**Caching (mandatory)**: Every Claude call cached in Redis 30 days, keyed by `sha256(prompt_version + input)`. Never call the API if a cached result exists.

**Quality gate (blocks publication)**:
1. `langdetect` returns `ar` with confidence > 0.95
2. Word count: 300–1500
3. No residual English (no >5 consecutive Latin chars in body, excluding allowlisted tech terms)
4. At least 2 H2 headings + 1 list
5. ≥80% of detected tech terms match `darija_glossary` entries
6. No `[TODO]`, `lorem ipsum`, or `<placeholder>` text

**Cost logging**: Every AI call → `ai_logs` table (tokens + computed cost). Sentry alert if daily spend > $5.

---

## 6. DATABASE RULES

**Migration policy (sacred)**:
- Never edit a migration merged to `main`. Always create a new one.
- Never `DROP COLUMN` directly — use the 5-PR expand/contract pattern.
- Migration filenames: `YYYYMMDD_HHMM_short_description.py`. Every migration has `upgrade()` + `downgrade()`.

**Schema rules**:
- All tables: `id` PK, `created_at`, `updated_at` (where mutable). Timestamps = `TIMESTAMPTZ`.
- Soft deletes: `deleted_at TIMESTAMPTZ NULL`, not `is_deleted BOOLEAN`.
- Enums: `VARCHAR + CHECK constraint`, not Postgres native ENUMs.
- All FKs have explicit `ON DELETE` (CASCADE / RESTRICT / SET NULL).
- Index every FK and every column used in `WHERE`/`ORDER BY` on hot queries.
- No N+1: use `selectinload` or joins on all list endpoints.

---

## 7. SECURITY RULES

- Secrets via Doppler only. Never in code, logs, or commits. `gitleaks` pre-commit hook enforces this.
- Public API: 60 req/min/IP. Admin endpoints: `Authorization: Bearer <jwt>` (HS256, 1h expiry).
- CORS: frontend origin only — no wildcard in prod.
- HTML sanitization: `bleach` on backend, `rehype-sanitize` on frontend. SQLAlchemy parameterized queries only — no raw SQL outside Alembic migrations.

---

## 8. WORKFLOW RULES

**Commits** (Conventional Commits format):
- `feat|fix|refactor|perf|docs|test|chore|style|ci(scope): subject ≤72 chars, imperative`
- Body = why, not what. Footer = `Fixes #N`.

**Branches**: `feat/<name>` or `fix/<name>`. No branch lives > 3 days. PRs required for `main`.

**Testing**:
- 80%+ line coverage on `services/`. Smoke tests (happy + 1 error path) on routes.
- Mock external APIs with `respx`. Never call real APIs in tests.
- Use real Postgres + Redis in integration tests (not mocks).
- Test through public service interface only — no private method tests.

**API conventions**: REST, `/api/v1/` prefix, cursor-based pagination, lists return `{ data: [...] }`.
Error shape: `{ error: { code: "SCREAMING_SNAKE", message: "...", request_id: "..." } }`.

---

## 9. HARD NO LIST

- No force-push to `main`. No committing `.env` or secrets.
- No sync I/O in async functions. No long-running tasks in API handlers (use background jobs).
- No `SELECT *` in production. No raw SQL outside migrations.
- No GPT for Arabic content — Claude only (validated better Darija quality).
- No new dependency without explicit justification — every dep is future maintenance.
- No inline prompts, no skipping the quality gate, no auto-publishing.
- No `any` in TypeScript. No client components when server would work.
- No Boolean flag columns accumulating — use a state enum.

---

## 10. EXTERNAL REFERENCES

| What | Where |
|---|---|
| Architecture rationale & ADRs | `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` |
| Prompt engineering log | `docs/PROMPTS.md` |
| Darija glossary | `docs/DARIJA_GLOSSARY.md` |
| All dev/deploy commands | `Makefile` |
| Full original CLAUDE.md | `claude.full.backup.md` |
