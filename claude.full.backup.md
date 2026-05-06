# CLAUDE.md

> **Purpose**: This is the canonical project context for AI coding assistants (Claude Code, Cursor, etc.). Read this file fully before making any code change. This is the source of truth for conventions, architecture, and decisions.
>
> **Last updated**: 2026-05-03 · **Version**: 1.0 · **Maintainer**: Solo founder

---

## 1. PROJECT IDENTITY

### Name
**DarijaAI** — Moroccan Darija AI News Platform

### One-liner
The first editorial-grade media platform delivering AI/tech news in Moroccan Darija through an AI-powered localization pipeline.

### Mission
Make state-of-the-art AI knowledge accessible to the Maghreb tech community in their native voice, building a defensible content moat in an underserved Arabic-language market.

### What this is NOT
- ❌ NOT a translation service (we localize editorially, not translate literally)
- ❌ NOT a no-code aggregator (we own the full stack for velocity)
- ❌ NOT a general news site (AI/tech-only, deep specialization)
- ❌ NOT a fully automated zero-touch system (human editorial review for first 100 articles minimum)

### Success metrics (Month 1)
- 5,000 unique visitors
- 200+ indexed articles on Google
- Lighthouse score ≥95 across all metrics
- Total infra cost ≤$50/month
- Zero incidents lasting >10 minutes

---

## 2. QUICK START COMMANDS

> Always run these from the **monorepo root** unless specified.

### First-time setup
```bash
# 1. Install system dependencies
brew install uv node@22 postgresql@16 redis    # macOS
# OR: curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone & bootstrap
git clone <repo-url> darija-ai && cd darija-ai
make setup          # runs all setup scripts (see Makefile)

# 3. Configure secrets
cp .env.example .env
doppler login && doppler setup    # preferred over raw .env

# 4. Run migrations
make db-migrate

# 5. Seed data
make seed
```

### Daily development
```bash
make dev            # runs backend + frontend concurrently
make backend        # backend only (FastAPI on :8000)
make frontend       # frontend only (Next.js on :3000)
make worker         # background worker (scheduler + jobs)
```

### Quality gates (run before EVERY commit)
```bash
make lint           # ruff + eslint + prettier --check
make typecheck      # mypy + tsc --noEmit
make test           # pytest + vitest
make check          # all of the above
```

### Database operations
```bash
make db-migrate                          # apply pending migrations
make db-revision msg="add foo column"    # create new migration
make db-rollback                         # rollback last migration
make db-reset                            # ⚠️  drop + recreate (dev only)
make db-shell                            # psql shell
```

### Deployment
```bash
git push origin main                     # auto-deploys via CI/CD
make deploy-backend                      # manual backend deploy
make logs-backend                        # tail Railway logs
make logs-frontend                       # tail Vercel logs
```

### One-shot operations
```bash
make fetch-articles                      # trigger manual scrape
make process-pending                     # process pending articles
make publish ARTICLE_ID=42               # publish specific article
make broadcast ARTICLE_ID=42             # social broadcast
```

---

## 3. ARCHITECTURE

### High-level flow
```
Sources (RSS/HTML) 
    → Scraper (Python, scheduled every 30min)
    → Raw Articles (Postgres)
    → Job Queue (Redis)
    → AI Pipeline (Claude → Quality Gate → Replicate)
    → Articles (Postgres) + Images (R2)
    → Frontend (Next.js, ISR) + Distribution (Social APIs + Email)
```

### Service boundaries
| Service | Tech | Role | Hosted on |
|---|---|---|---|
| `frontend` | Next.js 15 | Public site, admin UI | Vercel |
| `backend` | FastAPI | REST API, business logic | Railway |
| `worker` | Python + APScheduler | Scheduled jobs, async processing | Railway |
| `db` | PostgreSQL 16 | Primary store | Neon |
| `cache` | Redis | Job queue, response cache | Upstash |
| `storage` | S3-compatible | Generated images | Cloudflare R2 |

### Key architectural rules
1. **Frontend NEVER talks to the database directly.** Always through the FastAPI.
2. **Worker and backend share the same codebase** but different entrypoints. Same models, same services.
3. **All cross-service communication is HTTP+JSON** (no gRPC, no message brokers beyond Redis queues).
4. **The database is the source of truth**, not Redis. Redis is purely cache/queue.
5. **Idempotency is mandatory** for any job that can retry (use `url_hash` for dedup, job IDs for retries).

---

## 4. REPOSITORY STRUCTURE

```
darija-ai/
├── backend/                    # FastAPI + worker (Python)
│   ├── app/
│   │   ├── api/                # HTTP routes (thin controllers)
│   │   │   ├── v1/
│   │   │   │   ├── articles.py
│   │   │   │   ├── admin.py
│   │   │   │   └── ...
│   │   │   └── deps.py         # FastAPI dependencies
│   │   ├── core/               # Cross-cutting
│   │   │   ├── config.py       # Pydantic Settings
│   │   │   ├── db.py           # Async SQLAlchemy engine
│   │   │   ├── redis.py
│   │   │   ├── logging.py
│   │   │   ├── security.py
│   │   │   └── exceptions.py   # Custom exception hierarchy
│   │   ├── models/             # SQLModel tables (DB schema)
│   │   ├── schemas/            # Pydantic models (API I/O)
│   │   ├── services/           # Business logic (the meat)
│   │   │   ├── scraping/
│   │   │   ├── ai/
│   │   │   │   ├── claude_client.py
│   │   │   │   ├── replicate_client.py
│   │   │   │   ├── prompts/         # Versioned prompts
│   │   │   │   │   ├── localizer_v1.md
│   │   │   │   │   └── localizer_v2.md
│   │   │   │   ├── localizer.py
│   │   │   │   ├── image_generator.py
│   │   │   │   └── quality_gate.py
│   │   │   ├── distribution/
│   │   │   │   ├── linkedin.py
│   │   │   │   ├── meta.py
│   │   │   │   └── newsletter.py
│   │   │   └── publishing.py
│   │   ├── workers/            # Background jobs
│   │   │   ├── scheduler.py    # APScheduler entrypoint
│   │   │   ├── jobs/
│   │   │   │   ├── fetch_articles.py
│   │   │   │   ├── process_articles.py
│   │   │   │   └── distribute.py
│   │   │   └── main.py
│   │   ├── utils/
│   │   └── main.py             # FastAPI app entrypoint
│   ├── alembic/                # DB migrations
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── CLAUDE.md               # Backend-specific overrides
│
├── frontend/                   # Next.js 15 (TypeScript)
│   ├── src/
│   │   ├── app/                # App Router (RSC by default)
│   │   │   ├── (public)/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── article/[slug]/page.tsx
│   │   │   │   └── categorie/[slug]/page.tsx
│   │   │   ├── (admin)/
│   │   │   │   └── admin/...
│   │   │   ├── api/            # Route handlers (NOT business logic)
│   │   │   ├── layout.tsx
│   │   │   ├── sitemap.ts
│   │   │   ├── robots.ts
│   │   │   └── feed.xml/route.ts
│   │   ├── components/
│   │   │   ├── ui/             # shadcn/ui primitives
│   │   │   └── features/       # Feature-specific composites
│   │   ├── lib/
│   │   │   ├── api.ts          # Backend API client (typed)
│   │   │   ├── utils.ts
│   │   │   └── seo.ts
│   │   ├── styles/
│   │   ├── types/              # Shared TS types
│   │   └── config/
│   ├── public/
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   └── CLAUDE.md               # Frontend-specific overrides
│
├── shared/                     # Shared OpenAPI types (generated)
│   └── api-types.ts            # Generated from backend OpenAPI spec
│
├── infra/
│   ├── docker-compose.yml      # Local dev (postgres + redis)
│   ├── railway.json
│   └── scripts/
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROMPTS.md              # Prompt engineering log
│   ├── DARIJA_GLOSSARY.md
│   └── DECISIONS.md            # ADRs (Architecture Decision Records)
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── Makefile                    # All common commands
├── .env.example
├── .gitignore
├── README.md
└── CLAUDE.md                   # ← YOU ARE HERE (root context)
```

### Layer rules (strictly enforced)
- **`api/`** layer is THIN. Only validation + delegation to services. Zero business logic.
- **`services/`** is where business logic lives. Pure Python, framework-agnostic where possible.
- **`models/`** are DB tables. **`schemas/`** are API contracts. NEVER expose models directly via API.
- **`workers/`** call services. They do NOT contain business logic.
- **`utils/`** contains stateless pure functions only. If it has state or external I/O, it's a service.

---

## 5. TECH STACK (LOCKED VERSIONS)

### Backend
| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | 3.12 minimum, 3.13 preferred |
| Package manager | `uv` (latest) | NOT pip, NOT poetry |
| Web framework | FastAPI ≥0.115 | |
| ORM | SQLModel ≥0.0.22 | wraps SQLAlchemy 2.x |
| DB driver | `asyncpg` | async only |
| Migrations | Alembic | |
| HTTP client | `httpx` | async, replaces `requests` |
| Validation | Pydantic v2 | |
| Settings | `pydantic-settings` | |
| Scheduler | APScheduler 3.x | |
| Queue | `arq` (Redis-based) | not Celery |
| Scraping | `feedparser` + `selectolax` | selectolax > BeautifulSoup (10x faster) |
| JS-rendered scraping | Playwright (sparingly) | |
| Logging | `structlog` | structured JSON in prod |
| Error tracking | `sentry-sdk` | |
| Testing | `pytest` + `pytest-asyncio` + `httpx` | |
| Linting | `ruff` (lint + format) | replaces black + flake8 + isort |
| Type checking | `mypy --strict` | |
| AI SDK | `anthropic` | official |
| Image gen SDK | `replicate` | official |

### Frontend
| Tool | Version | Notes |
|---|---|---|
| Runtime | Node 22 LTS | |
| Package manager | `pnpm` | NOT npm, NOT yarn |
| Framework | Next.js 15 | App Router only, no Pages Router |
| Language | TypeScript 5.6+ | `strict: true`, NO `any` |
| Styling | Tailwind CSS v4 | with `tailwindcss-rtl` |
| UI components | shadcn/ui | copy-paste, NOT a dependency |
| Icons | `lucide-react` | |
| Forms | `react-hook-form` + `zod` | |
| Data fetching | RSC + native `fetch` | NOT swr/react-query for server data |
| Client state | `zustand` | only if absolutely needed |
| Markdown | `react-markdown` + `rehype-sanitize` | XSS protection mandatory |
| Analytics | Vercel Analytics + Plausible | |
| Linting | ESLint + Prettier | |
| Testing | Vitest + Testing Library | |
| E2E (later) | Playwright | |

### Infrastructure
| Service | Provider | Plan |
|---|---|---|
| Frontend | Vercel | Hobby (free) |
| Backend | Railway | Hobby ($5/mo) |
| Database | Neon | Free (3GB) |
| Redis | Upstash | Free (10K cmd/day) |
| Object storage | Cloudflare R2 | Free (10GB) |
| CDN | Cloudflare | Free |
| DNS | Cloudflare | Free |
| Email | Resend | Free (3K/mo) |
| Monitoring | Sentry + Uptime Robot | Free |
| Secrets | Doppler | Free dev tier |

### AI Providers
| Service | Use | Model | Notes |
|---|---|---|---|
| Anthropic | Localization (PRODUCTION) | `claude-haiku-4-5` | Single-pass per ADR-002. Mandatory human review in admin panel. $1 / $5 per 1M tokens. |
| Anthropic | Opt-in for flagship articles | `claude-sonnet-4-6` | Pass `model="claude-sonnet-4-6"` to Localizer. $3 / $15 per 1M tokens. |
| OpenAI | Cross-model critic (kept available, not in prod) | `gpt-4o-mini` | $0.15 / $0.60 per 1M tokens. |
| Replicate | Image generation | `black-forest-labs/flux-schnell` | |

---

## 6. BACKEND CONVENTIONS

### Python style (strictly enforced)
```python
# ✅ DO: Type hints on everything
async def fetch_article(url: str) -> RawArticle | None:
    ...

# ❌ DON'T: Untyped functions
def fetch_article(url):
    ...

# ✅ DO: Modern union syntax (Python 3.10+)
def get(id: int) -> Article | None:
    ...

# ❌ DON'T: Optional[X], Union[X, Y]
def get(id: int) -> Optional[Article]:
    ...

# ✅ DO: Dataclasses or Pydantic for structured data
class ArticleInput(BaseModel):
    title: str
    content: str

# ❌ DON'T: Dicts as pseudo-objects
def process(data: dict[str, Any]):  # avoid
    ...
```

### Async rules
- **Default to async** for any I/O-bound code (DB, HTTP, file).
- **Use `asyncio.gather()`** for parallel I/O. Never `await` in a loop when independent.
- **Sync code only** for pure CPU work (parsing, computation).
- **NEVER mix sync DB calls in async code** — use `asyncpg` exclusively.

```python
# ✅ DO: Parallel I/O
results = await asyncio.gather(
    claude.translate(article),
    replicate.generate_image(article),
)

# ❌ DON'T: Sequential when independent
translation = await claude.translate(article)
image = await replicate.generate_image(article)  # could've run in parallel
```

### Service layer pattern
Every service is a class with explicit dependencies, instantiated once per request via FastAPI's dependency system.

```python
# app/services/ai/localizer.py
class Localizer:
    def __init__(
        self,
        claude: ClaudeClient,
        cache: RedisCache,
        glossary: GlossaryRepo,
    ):
        self._claude = claude
        self._cache = cache
        self._glossary = glossary

    async def localize(self, raw: RawArticle) -> LocalizedArticle:
        cached = await self._cache.get(raw.url_hash)
        if cached:
            return cached
        # ... business logic
        result = await self._claude.complete(...)
        await self._cache.set(raw.url_hash, result, ttl=86400 * 30)
        return result
```

### FastAPI patterns
```python
# ✅ Routes are thin
@router.post("/articles/{id}/publish", response_model=ArticleOut)
async def publish_article(
    id: int,
    publisher: PublishingService = Depends(get_publisher),
    user: AdminUser = Depends(require_admin),
) -> ArticleOut:
    article = await publisher.publish(id, user.id)
    return ArticleOut.from_model(article)

# ❌ Routes don't contain business logic, DB queries, or external API calls
@router.post("/articles/{id}/publish")  # AVOID
async def publish_article(id: int, db: Session = Depends(get_db)):
    article = await db.get(Article, id)
    article.is_published = True
    await db.commit()
    # ... 50 more lines of logic
```

### Error handling
- **Custom exception hierarchy** in `app/core/exceptions.py`:
  ```python
  class AppError(Exception): ...
  class NotFoundError(AppError): ...
  class ValidationError(AppError): ...
  class ExternalServiceError(AppError): ...
  class AIQualityError(AppError): ...
  ```
- **Single global exception handler** maps these to HTTP status codes.
- **NEVER catch `Exception`** without re-raising or logging with full context.
- **External API calls** wrapped with retry (tenacity) + timeout + Sentry breadcrumbs.

### Logging
```python
# ✅ Structured logging
logger.info("article.localized", article_id=42, duration_ms=1234, tokens_used=890)

# ❌ String formatting in logs
logger.info(f"Localized article {id} in {duration}ms")  # not queryable
```

- Log levels: `DEBUG` (dev only), `INFO` (business events), `WARNING` (recoverable), `ERROR` (needs attention), `CRITICAL` (page someone).
- Every external API call: log start + end + duration + cost.
- Every job: log start + end + outcome.

---

## 7. FRONTEND CONVENTIONS

### TypeScript rules (zero tolerance)
```ts
// tsconfig.json non-negotiables
{
  "strict": true,
  "noUncheckedIndexedAccess": true,
  "noImplicitOverride": true,
  "noFallthroughCasesInSwitch": true
}
```

- **NO `any`**. Use `unknown` and narrow.
- **NO `as` casts** unless you've exhausted other options. Document why with a comment.
- **NO non-null assertions (`!`)** in production code.
- **Discriminated unions over optional fields** for state.

```ts
// ✅ DO
type FetchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: Article[] }
  | { status: "error"; error: string };

// ❌ DON'T
type FetchState = {
  loading: boolean;
  error: string | null;
  data: Article[] | null;
};
```

### React Server Components (RSC) rules
- **Default to Server Components.** Mark `"use client"` only when:
  - Using `useState`, `useEffect`, browser APIs, event handlers
  - Using third-party client-only libs
- **Push `"use client"` boundaries as low as possible** in the tree.
- **Fetch data in Server Components**, pass data down. NO client-side fetching for initial render.
- **Pass server functions as props (Server Actions)** for mutations from client components.

```tsx
// ✅ DO: Fetch in RSC, pass to client island
// app/page.tsx (server)
export default async function HomePage() {
  const articles = await api.articles.list({ limit: 10 });
  return <ArticleGrid articles={articles} />;
}

// components/ArticleGrid.tsx (client only if needed for interactivity)
"use client";
export function ArticleGrid({ articles }: { articles: Article[] }) {
  // ... interactive UI
}
```

### Styling rules
- **Tailwind utility-first**, no custom CSS files except `globals.css`.
- **Use `cn()` helper** (clsx + tailwind-merge) for conditional classes.
- **Design tokens via CSS variables** in `globals.css`, referenced by Tailwind config.
- **NO inline styles** except for dynamic values (e.g., `style={{ width: ${pct}% }}`).

### RTL & Arabic typography
- `<html lang="ar-MA" dir="rtl">` in root layout — NEVER changes.
- **Use logical properties**: `ms-4` (margin-start) NOT `ml-4` (margin-left).
- **Tailwind plugin `tailwindcss-rtl`** is mandatory.
- **Font**: Tajawal via `next/font/google`, preloaded.
- **Latin numerals** for stats (years, percentages) inside Arabic text — readable mixed style.
- **Punctuation**: Use Arabic comma `،` and Arabic question mark `؟` in display text.

### SEO requirements (every page)
- `generateMetadata()` exported from every route — no fallback to defaults.
- Open Graph image required (1200×630, served from R2 CDN).
- Canonical URL set.
- Schema.org JSON-LD for article pages (`NewsArticle` type).
- `lang="ar"` and `dir="rtl"` declared.

```tsx
// app/article/[slug]/page.tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const article = await api.articles.bySlug(params.slug);
  return {
    title: article.metaTitle,
    description: article.metaDescription,
    openGraph: {
      type: "article",
      images: [{ url: article.heroImageUrl, width: 1200, height: 630 }],
      locale: "ar_MA",
      publishedTime: article.publishedAt,
    },
    alternates: { canonical: `https://darija-ai.com/article/${article.slug}` },
  };
}
```

### Performance hard requirements
- LCP < 2.0s (mobile, 4G)
- CLS < 0.05
- INP < 200ms
- Total JS shipped to client per page < 100kb gzipped
- All images via `next/image` with explicit `width`/`height`

---

## 8. AI INTEGRATION GUIDELINES

### Prompts are code
- **Prompts live in `backend/app/services/ai/prompts/*.md`**.
- **Versioned by filename**: `localizer_v1.md`, `localizer_v2.md`, never edit a deployed version.
- **Active version pinned in config**: `LOCALIZER_PROMPT_VERSION=v2`.
- **A/B testing**: pin different versions per source for evaluation.
- **Every prompt change goes through PR review** with at least 5 sample outputs attached.

### Claude API usage
```python
# ✅ DO: Always set max_tokens, system, structured input
response = await claude.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=load_prompt("localizer_v2"),
    messages=[{"role": "user", "content": user_input}],
    metadata={"user_id": "system", "raw_article_id": str(article.id)},
)

# ❌ DON'T: Hardcode prompts inline
response = await claude.messages.create(
    messages=[{"role": "user", "content": f"Translate this to Darija: {article}"}]
)
```

### Cost control (mandatory)
1. **Cache by content hash**: every Claude response cached in Redis 30 days, keyed by `sha256(prompt_version + input)`.
2. **Daily budget alarm**: Sentry alert if daily cost > $5.
3. **Per-request cost logging**: every call logged in `ai_logs` table with token count + computed cost.
4. **No retries on quality failures** — if quality gate fails 2x, mark `rejected` and move on.
5. **Use Sonnet for production, Haiku for testing**: Haiku is 12x cheaper, good for dev.

### Quality Gate (non-negotiable for publishing)
Before any article is marked `is_published=true`, it MUST pass:

1. **Language detection**: `langdetect` returns `ar` with confidence > 0.95
2. **Word count**: 300 ≤ words ≤ 1500
3. **No residual English**: no English sentences (heuristic: regex match for >5 consecutive Latin chars in body, excluding allowlisted tech terms)
4. **Required structure**: at least 2 H2 headings, at least 1 list
5. **Glossary compliance**: at least 80% of detected technical terms match glossary entries
6. **No placeholder text**: no `[TODO]`, `lorem ipsum`, `<placeholder>`, etc.

If any check fails → status = `rejected`, log reason, alert if rejection rate > 30%.

### Image generation
- **Style guide locked in `image_generator.py`**: editorial, abstract, blue/purple gradient, no text, no humans
- **Always 1024×576** (16:9 for OG)
- **Always upload to R2 with hash-based filename** (immutable, cacheable forever)
- **Fallback**: if Replicate fails 3x, use a curated default image per category

---

## 9. DATABASE

### Migration policy (sacred)
- **NEVER edit a migration that has been merged to `main`.** Always create a new one.
- **NEVER use `DROP COLUMN` directly.** Use the expand/contract pattern:
  1. PR 1: Add new column nullable
  2. PR 2: Backfill data
  3. PR 3: Make non-null + start writing only there
  4. PR 4: Stop reading old column
  5. PR 5: Drop old column (separate, easily revertable)
- **Migration filenames**: `YYYYMMDD_HHMM_short_description.py`
- **Every migration has `upgrade()` AND `downgrade()`**, both tested locally.

### Schema rules
- **All tables have**: `id` (PK), `created_at`, `updated_at` (where mutable)
- **Timestamps are `TIMESTAMPTZ`** (always UTC, never naive).
- **Money/cost stored as `DECIMAL(10, 6)`** USD, never float.
- **Enums via VARCHAR + CHECK constraint**, not Postgres native ENUMs (easier to migrate).
- **Soft deletes via `deleted_at TIMESTAMPTZ NULL`**, NOT `is_deleted BOOLEAN`.
- **Foreign keys ALWAYS have `ON DELETE` defined explicitly** (CASCADE / RESTRICT / SET NULL).
- **Indexes on every FK and every column used in WHERE/ORDER BY** in hot queries.

### Naming conventions
- Tables: `snake_case`, plural (`articles`, `raw_articles`)
- Columns: `snake_case`
- Indexes: `idx_<table>_<columns>` (e.g., `idx_articles_published_at`)
- Foreign keys: `<table>_id` (e.g., `source_id`)
- Booleans: `is_*` or `has_*` (`is_published`, `has_image`)

---

## 10. API DESIGN

### REST conventions
- **Versioned URL prefix**: `/api/v1/...`. Breaking changes go to `/v2`.
- **Plural resource names**: `/articles`, not `/article`.
- **HTTP verbs respected**: GET (read), POST (create), PATCH (partial update), PUT (replace), DELETE (delete).
- **NO RPC-style endpoints** like `/api/v1/doSomething`. Use POST `/<resource>/<id>/<action>` for actions.

### Standard error response
```json
{
  "error": {
    "code": "ARTICLE_NOT_FOUND",
    "message": "Article with id 42 not found",
    "details": {},
    "request_id": "req_abc123"
  }
}
```

- `code` is `SCREAMING_SNAKE_CASE`, stable, documented.
- `message` is human-readable English (i18n only on frontend).
- `request_id` is logged and traceable in Sentry.

### Pagination (cursor-based, not offset)
```http
GET /api/v1/articles?limit=20&cursor=eyJpZCI6MTIzfQ==

{
  "data": [...],
  "next_cursor": "eyJpZCI6MTQzfQ==",
  "has_more": true
}
```

### Response shape rules
- **Lists return `{ data: [...], ... }`**, never bare arrays.
- **Snake_case in JSON** (matches Python). Frontend converts to camelCase at the boundary in `lib/api.ts`.
- **Dates as ISO 8601 with timezone**: `2026-05-03T14:30:00Z`.
- **NEVER expose internal IDs that aren't meant to be public** — use UUIDs for public-facing entities, integer IDs for internal.

---

## 11. SECURITY

### Secrets (zero exceptions)
- **Doppler for secret management** in dev, staging, prod.
- **`.env` is git-ignored**. `.env.example` has every var with safe placeholder.
- **NEVER log secrets**. The logger has a redaction filter on common patterns.
- **NEVER commit secrets**. Pre-commit hook scans for them (`gitleaks`).
- **Rotate API keys** quarterly minimum.

### Authentication
- **Public site**: no auth required.
- **Admin panel**: NextAuth.js with email magic link (Resend) — single admin user initially.
- **Backend admin endpoints**: protected by `Authorization: Bearer <admin_jwt>` header.
- **JWT secret rotated quarterly**, signed HS256, 1h expiry, refresh tokens 30 days.

### Rate limiting
- **Public API**: 60 req/min per IP via Upstash Ratelimit.
- **Admin API**: 600 req/min per user.
- **Newsletter signup**: 5/hour per IP (anti-spam).
- **AI endpoints**: 10/min per user (cost protection).

### CORS
- **Frontend origin only** in `allow_origins`. NO wildcard in prod.
- **Specific methods only**, not `["*"]`.

### Input validation
- **Every Pydantic schema validates aggressively**: max lengths, regex on slugs, URL validation.
- **Sanitize HTML** (when rendering Darija content with markdown): `bleach` on backend, `rehype-sanitize` on frontend.
- **SQL injection**: SQLAlchemy parametrized queries only. Raw SQL forbidden except in Alembic migrations.

---

## 12. TESTING STRATEGY

### Coverage targets
- **Backend services**: 80%+ line coverage (the business logic).
- **API routes**: smoke tests on happy path + 1 error path each.
- **Models / schemas**: trust the framework, no tests.
- **Workers / jobs**: integration tests with fake external APIs.
- **Frontend**: component tests for interactive components only. E2E for 3 critical paths.

### What to test (priority order)
1. **AI pipeline**: localization → quality gate → image gen (mocked APIs)
2. **Scraping deduplication**: never publish same article twice
3. **Publishing flow**: state transitions are correct
4. **Admin auth**: unauthorized requests are rejected
5. **API contracts**: response shapes match schemas

### Test patterns
```python
# ✅ DO: Test through public service interface
async def test_localizer_caches_responses(localizer, claude_mock, redis):
    article = make_raw_article()
    await localizer.localize(article)
    await localizer.localize(article)
    assert claude_mock.call_count == 1  # second call hit cache

# ❌ DON'T: Test private methods or internal implementation
async def test_localizer__build_prompt():  # double underscore = private, don't
    ...
```

- **Use factories** (`factory_boy` or simple functions) for test data.
- **Mock external APIs**, never call real APIs in tests (use `respx` for httpx).
- **Use real Postgres + Redis** in integration tests (Testcontainers or a test DB).

---

## 13. GIT & COMMIT CONVENTIONS

### Branching
- **Trunk-based development**: `main` is always deployable.
- **Feature branches**: `feat/<short-description>` or `fix/<short-description>`.
- **No long-lived branches** beyond 3 days.
- **Pull requests required** for `main`, even solo (forces review-via-CI).

### Commit messages (Conventional Commits)
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `style`, `ci`.

Examples:
```
feat(ai): add quality gate for Darija output
fix(scraping): handle empty RSS feeds without crashing
refactor(api): extract publishing logic to service layer
chore(deps): bump anthropic to 0.40.0
```

- Subject ≤72 chars, imperative mood ("add", not "added").
- Body explains WHY, not what (the diff shows what).
- Reference issues: `Fixes #42` in footer.

### Pre-commit hooks (`pre-commit` framework)
- `ruff check --fix`
- `ruff format`
- `mypy`
- `eslint --fix`
- `prettier --write`
- `gitleaks` (secret scanner)
- `commitizen` (commit message format check)

---

## 14. DEPLOYMENT

### Environments
- **Local**: developer machine, Docker Compose for DB/Redis
- **Staging**: Railway preview env, branch `staging`, real APIs but separate DB
- **Production**: Railway prod env, branch `main`, full monitoring

### CI/CD pipeline (`.github/workflows/`)
**On every PR:**
1. Lint (ruff, eslint)
2. Type check (mypy, tsc)
3. Tests (pytest, vitest)
4. Build (next build, docker build)

**On merge to `main`:**
1. All of above
2. Deploy backend to Railway
3. Deploy frontend to Vercel
4. Run database migrations
5. Smoke tests against staging
6. Notify Sentry of release

### Rollback
- **Frontend**: Vercel instant rollback (1-click in dashboard).
- **Backend**: Railway redeploy previous build.
- **Database**: NEVER auto-rollback migrations. Manual fix-forward only.

### Release tagging
- Semantic versioning: `v1.2.3`
- Tag every prod release: `git tag v1.2.3 && git push --tags`
- Generate changelog: `git-cliff` on tag.

---

## 15. OBSERVABILITY

### Logging
- **Structured JSON in prod**, human-readable in dev.
- **Correlation ID** (`request_id`) on every log line in a request.
- **Standard fields**: `service`, `env`, `version`, `request_id`, `user_id` (if authenticated).
- **Levels used correctly** (see logging section above).

### Metrics (Sentry Performance)
- Every HTTP request traced.
- Every external API call as a span.
- Every job execution as a transaction.
- P95 latency dashboards reviewed weekly.

### Alerts
| Alert | Threshold | Channel |
|---|---|---|
| Backend down | 2 consecutive failed pings | Email + SMS |
| Error rate | >1% over 5min | Email |
| AI cost daily | >$5 | Email |
| Scraping silent | 0 new articles in 24h | Email |
| DB connection failures | Any | SMS |

### Dashboards
- **Sentry**: errors, performance, releases.
- **Vercel Analytics**: web vitals, traffic.
- **Plausible**: behavior, sources.
- **Custom admin**: AI cost, articles published, queue depth.

---

## 16. PERFORMANCE TARGETS

### Frontend
- **LCP**: < 2.0s (mobile 4G)
- **CLS**: < 0.05
- **INP**: < 200ms
- **TBT**: < 200ms
- **JS bundle per page**: < 100kb gzipped
- **Image hero**: WebP/AVIF, lazy except first
- **Lighthouse**: 95+ Performance, 100 SEO, 95+ Accessibility

### Backend
- **API p50 latency**: < 100ms
- **API p95 latency**: < 500ms
- **Article processing time**: < 60s end-to-end (scrape → published)
- **Memory per worker**: < 512MB

### Database
- **Query p95**: < 50ms
- **No N+1 queries**: every list endpoint uses joins or `selectinload`.
- **Connection pool**: 5-20 connections per service.

---

## 17. WHAT NOT TO DO (anti-patterns)

These are mistakes I want AI assistants to actively guard against. **If I ask for any of these, push back.**

### General
- ❌ Adding a dependency without justifying it (every dep = future maintenance)
- ❌ Premature abstraction (write the code 3 times before extracting)
- ❌ "Refactoring" while implementing a feature (separate PRs)
- ❌ Adding TODO comments without tracking issues
- ❌ Commenting out code (delete it, git remembers)
- ❌ Catching exceptions to hide them
- ❌ Adding logs/prints for debugging that ship to prod

### Backend
- ❌ Sync I/O in async functions (blocks the event loop)
- ❌ Long-running tasks in API handlers (use background jobs)
- ❌ Raw SQL except in migrations (use SQLModel)
- ❌ Returning ORM objects from API endpoints (always Pydantic schemas)
- ❌ Storing config in code (use Settings class)
- ❌ Hardcoded URLs / API keys / IDs

### Frontend
- ❌ `any` in TypeScript (use `unknown` or define the type)
- ❌ Client components when server would work
- ❌ Fetching data on the client for SEO-critical content
- ❌ `useEffect` for derived state (compute during render)
- ❌ Direct DOM manipulation (use refs sparingly)
- ❌ Inline styles for non-dynamic values
- ❌ Importing heavy libraries client-side (check bundle size)

### AI
- ❌ Building prompts with f-strings inline in business logic
- ❌ Calling Claude without caching when input is deterministic
- ❌ Skipping the quality gate "just this once"
- ❌ Logging the full prompt content in production (use hash)
- ❌ Using GPT instead of Claude for Arabic (Claude is significantly better)

### Database
- ❌ Schema changes without migrations
- ❌ Querying in loops (N+1)
- ❌ Storing JSON blobs when columns would do
- ❌ Boolean flags accumulating (consider state enum)
- ❌ `SELECT *` in production code

### Git
- ❌ Force-pushing to `main`
- ❌ Committing `.env` or any secret
- ❌ Massive PRs (>500 lines without strong reason)
- ❌ Generic commit messages ("fix stuff", "wip")

---

## 18. DECISION LOG (key choices and rationale)

### Why Python (FastAPI) for backend, not Node?
AI ecosystem is Python-first. We use Anthropic, Replicate, scraping libs (`feedparser`, `selectolax`), language detection (`langdetect`). Mixing two languages adds zero value here.

### Why Next.js, not SvelteKit / Astro / Remix?
- Best Vercel integration (free hobby tier).
- Best ecosystem for Arabic/RTL (Tailwind plugin, fonts, examples).
- ISR is critical for our use case (frequent publishing, but content static once published).
- Largest pool of Claude/AI training data for code generation.

### Why Neon for Postgres, not Supabase?
- Neon's free tier is more generous for our shape (3GB, branching).
- We don't need Supabase's auth/storage (we use NextAuth + R2).
- Neon's branching enables preview env DB clones effortlessly.

### Why `uv` not poetry?
- 10-100x faster install / resolve.
- Drop-in pip-compatible.
- Active development, used by Astral (ruff team) — same quality bar.

### Why `arq` not Celery for queues?
- Celery is over-engineered for our needs.
- arq is async-native, simpler, fewer moving parts.
- Solo dev = minimize operational surface.

### Why Replicate (Flux) not Leonardo / DALL-E / Midjourney?
- Flux Schnell on Replicate: $0.003/image vs Leonardo's ~$0.02.
- Quality is comparable or better for our editorial style.
- API is dead simple.

### Why no GraphQL?
- Solo project, single client (our frontend), known query patterns.
- REST + OpenAPI codegen gives us type safety with zero overhead.
- GraphQL pays off with multiple clients and complex relationships — not us.

### Why Anthropic for localization?
- Best Arabic/Darija performance among current model families (validated against GPT-4o-mini and against same-family Sonnet critic in cross-model test).
- Long context handles full source articles + glossary + few-shots in one prompt.
- Production model selection is in ADR-002 below: Haiku 4.5 by default, Sonnet 4.6 opt-in for flagships.

> **Note**: Sonnet 4.7 was mentioned in early planning but was never released by Anthropic. The Sonnet ID currently in production-eligible lists is 4.6.

### ADR-002: Haiku 4.5 single-pass + mandatory human review (2026-05-04)

After A/B/D/E testing on real article #4 (Salesforce Slackbot, ~1000 EN words):
- Mode A (Haiku-only): $0.041, 1111 words, quality 'good but with translated patterns'
- Mode B (Sonnet-only): $0.111, 866 words, quality 'excellent, native Moroccan flow'
- Mode D (Cross-model Haiku→GPT-mini→Haiku): $0.072, 1050 words, comparable to Sonnet, BUT GPT hallucinated reverse-RTL Arabic in `suggested_fix` (e.g. 'يكذ ليكو' instead of 'وكيل ذكي'). Haiku rewriter caught this case, but the risk is non-deterministic at scale.
- Mode E (OpenAI sanity): mechanical validation only, GPT writes weak Darija (MSA-leaning).

**Decision**: Mode A (Haiku 4.5 single-pass) for production. **All output is reviewed by the project owner — a Moroccan native speaker — in the admin panel before publication.** Articles are created as drafts (`is_published=False`); only the "Publish" button in the admin UI flips them live.

**Rationale**:
1. **Volume**: 3-4 articles/day. Annual savings vs Sonnet: ~$96/year.
2. **Human-in-the-loop is the QA layer.** Haiku produces good-but-imperfect Darija (~10-15% rough patches per Mode A test). The owner catches these in review — relying on the model alone is not the design.
3. **System prompt v1.2** addresses the most common failure modes: anti-translation patterns, English filler list, takeaway specificity.
4. **Sonnet is opt-in** for flagship pieces by passing `model="claude-sonnet-4-6"` to the Localizer.
5. **Cross-model code preserved** in `app/services/ai/cross_model_pipeline.py` and `prompts/critic_v1.md` / `prompts/rewriter_v1.md` for re-evaluation when GPT's RTL behavior is fixed.

**Cost estimate**: ~$5/month at 4 articles/day (~$60/year).

**Workflow**:
RSS scraper → Localizer (Haiku) → Image gen → Article saved as **draft** → Human reviews in admin → "Publish" button → distribution triggered.

**Validation artifacts**: `docs/test-results/2026-05-04-localizer-comparison/`.

---

## 19. INSTRUCTIONS FOR AI ASSISTANTS (Claude Code, Cursor)

### Before writing any code
1. **Read this file fully.** If something contradicts what I'm asking, surface the conflict.
2. **Read the relevant module's `CLAUDE.md`** if exists (`backend/CLAUDE.md`, `frontend/CLAUDE.md`).
3. **Check existing patterns** in similar files. Follow them.
4. **Verify dependencies are already installed** before suggesting `pip install` / `pnpm add`.

### When writing code
1. **Match the style of surrounding code** (formatting, naming, comments).
2. **Prefer composition over abstraction** — explicit > clever.
3. **Add types** to every Python function and TS function signature.
4. **Handle errors explicitly** — never swallow exceptions.
5. **Write tests for new business logic** — at least one happy path + one error path.

### When uncertain
1. **Ask before adding a new dependency.** Every dep is a long-term cost.
2. **Ask before changing a public API contract** (REST endpoints, exported functions).
3. **Ask before changing a migration that's been merged.**
4. **Make a recommendation, don't ask open-ended questions.** "I see two approaches: A and B. I recommend A because X. OK to proceed?" — not "What should we do here?"

### When the user is wrong
- **Push back if a request violates this document.** Cite the section.
- **Push back if a request introduces a known anti-pattern.**
- **Suggest the right approach with rationale**, then defer if user insists.

### Output expectations
- **Concise responses.** Skip preamble like "Great question!" — get to work.
- **Show diffs, not full files** when modifying existing code.
- **Group related changes** in one response, don't fragment unnecessarily.
- **Highlight side effects** (migrations needed, env vars added, deps installed).
- **End with what's left** — what tests to run, what to deploy, what's untested.

### Specific to this codebase
- **Darija content is sacred**: never auto-edit Darija strings without explicit instruction. The system prompt is the only thing producing them.
- **The glossary table is canonical**: when in doubt about a term, check `darija_glossary` first.
- **Cost matters**: this runs on a $50/mo budget. Always think cache-first when calling AI APIs.
- **Mobile-first**: ~70% of Moroccan traffic is mobile. Every UI decision tested at 375px width.
- **RTL is not "nice to have"**: it's the primary rendering mode. LTR is the exception.

---

## 20. APPENDIX: COMMON GOTCHAS

### "Why is my Darija text rendering left-to-right?"
- Check `<html dir="rtl">` is set.
- Check the text isn't wrapped in a component with explicit `dir="ltr"`.
- Mixed content (Arabic + Latin tech terms) may need `<bdi>` tags for proper isolation.

### "Why are my Sentry errors missing context?"
- Set `request_id` in middleware, propagate via context vars.
- Use `sentry_sdk.set_tag` and `set_user` early in the request lifecycle.

### "Why is the article stuck in `processing`?"
- Check Redis queue depth: `redis-cli LLEN arq:queue:default`
- Check worker logs for exceptions
- Check `ai_logs` for the latest entry — if `success=false`, look at error.

### "Why are images broken?"
- Check R2 bucket public access: should be enabled for `darija-ai-images` bucket.
- Check Cloudflare cache: purge if you changed an image URL.
- Check `next.config.ts` `images.remotePatterns` includes R2 domain.

### "Why is the site slow on mobile?"
- Check JS bundle: `pnpm analyze` should show < 100kb per route.
- Check that hero images are using `next/image` with `priority` only above the fold.
- Check that fonts use `display: swap` and are preloaded.

---

**End of CLAUDE.md** · Keep this up to date. When you make a major decision, log it in section 18.
