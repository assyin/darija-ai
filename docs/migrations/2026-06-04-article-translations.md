# Migration plan — `articles` → `article_translations`

**Authors**: Yassine (CTO), Claude (advisor)
**Date**: 2026-06-04
**Status**: 📐 Design only — execution gated behind `ai_logs` fix landing in prod
**ADR reference**: [ADR-003 — Normalize multilingual content](../DECISIONS.md#adr-003-normalize-multilingual-content-into-article_translations)

> **This is a design document.** It is NOT yet a checklist of work to execute. It exists to surface every decision, risk, and rollback path **before** the first SQL line is written, so the actual migration PRs are predictable.

---

## 1. Scope

In scope:

- Rename / split `articles` into `articles` (spine) + `article_translations` (per-locale).
- Backfill the 50 existing articles into 2 translation rows each (ar-MA + fr).
- Update services, schemas, admin UI, public pages, sitemap, RSS to read from the new shape.
- Wire `ai_logs.raw_article_id` ↔ `article_translations` provenance.

Out of scope:

- Multilingual expansion (MSA, EN, ES) — separate product decisions, post-migration.
- Switching FR from translator (Darija → FR) to localizer (EN → FR). That becomes a config change after the schema lands.
- Editorial prompt updates.
- CMS migration (rejected in ADR-003, Alternative D).

---

## 2. Pre-conditions (hard gates)

| # | Gate | How to verify | Owner |
|---|---|---|---|
| 1 | `ai_logs` populated in prod | `SELECT COUNT(*) FROM ai_logs WHERE created_at > NOW() - INTERVAL '24 hours' > 0` | this PR (`fix/ai-logs-cost-tracking`) |
| 2 | At least 7 days of `ai_logs` data captured | Sanity check baseline cost/article before migration alters writer paths | calendar gate |
| 3 | Backend test coverage measured on `models/article.py`, `api/v1/articles.py`, `services/pipeline/*` | `pytest --cov=app.models.article --cov=app.api.v1.articles --cov=app.services.pipeline` ≥ 80% on these paths | preparatory PR |
| 4 | Production DB backup + restore procedure verified | `pg_dump` → fresh restore on a staging-like Docker container, app boots, articles render | preparatory PR |
| 5 | Read-only feature flag in place (`READ_FROM_TRANSLATIONS_TABLE=false`) | env var honored in `articles` API | step 2 of expand phase |

**If any gate fails, the migration does not start.**

---

## 3. Target schema

### `articles` (spine — language-agnostic)

```sql
CREATE TABLE articles (
  id                      INTEGER PRIMARY KEY,
  slug                    VARCHAR(255) UNIQUE NOT NULL,
  raw_article_id          INTEGER NOT NULL REFERENCES raw_articles(id) ON DELETE RESTRICT,
  hero_image_url          TEXT,
  hero_image_alt          TEXT,
  categories              VARCHAR[] NOT NULL DEFAULT '{}',
  tags                    VARCHAR[] NOT NULL DEFAULT '{}',
  canonical_locale        VARCHAR(8)  NOT NULL DEFAULT 'ar-MA',
  is_globally_published   BOOLEAN     NOT NULL DEFAULT FALSE,
  views_count             INTEGER     NOT NULL DEFAULT 0,
  created_at              TIMESTAMPTZ NOT NULL,
  updated_at              TIMESTAMPTZ NOT NULL,
  deleted_at              TIMESTAMPTZ
);

CREATE INDEX idx_articles_raw_article_id      ON articles(raw_article_id);
CREATE INDEX idx_articles_categories          ON articles USING gin (categories);
CREATE INDEX idx_articles_tags                ON articles USING gin (tags);
CREATE INDEX idx_articles_globally_published  ON articles(is_globally_published, created_at DESC);
```

### `article_translations` (one row per `(article_id, locale)`)

```sql
CREATE TABLE article_translations (
  id                      BIGSERIAL PRIMARY KEY,
  article_id              INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  locale                  VARCHAR(8) NOT NULL,

  title                   TEXT NOT NULL,
  excerpt                 TEXT NOT NULL,
  content                 TEXT NOT NULL,
  meta_title              TEXT,
  meta_description        TEXT,
  reading_time_minutes    INTEGER,
  word_count              INTEGER,

  -- Editorial lifecycle (independent per locale)
  status                  VARCHAR(20) NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','review','published','archived')),
  published_at            TIMESTAMPTZ,
  human_reviewed_at       TIMESTAMPTZ,
  human_reviewer_id       INTEGER,

  -- Provenance / cost attribution
  source_locale           VARCHAR(8),     -- NULL or 'en' = direct from RSS; 'ar-MA' = translated from Darija
  generation_method       VARCHAR(20) NOT NULL
                          CHECK (generation_method IN ('localize','translate','human')),
  ai_provider             VARCHAR(20),
  ai_model                VARCHAR(50),
  prompt_version          VARCHAR(20),

  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (article_id, locale)
);

CREATE INDEX idx_at_locale_status_published  ON article_translations(locale, status, published_at DESC);
CREATE INDEX idx_at_article_id               ON article_translations(article_id);
```

**Notes on schema choices**:

- `VARCHAR + CHECK` for enums (CLAUDE.md §6, no native ENUMs).
- All timestamps `TIMESTAMPTZ` (CLAUDE.md §6).
- `BIGSERIAL` on `article_translations.id` because this table grows N× faster than `articles` — 5 locales × growth.
- `ON DELETE CASCADE` from translations to article — a deleted article necessarily takes its translations with it.
- No `deleted_at` on translations — soft-delete at the article level only; un-publishing a translation is `status='archived'`.
- `slug` remains on `articles` (one slug per article, shared across locales) — this is intentional: `/fr/articles/<slug>` and `/articles/<slug>` resolve to the same article, different translation.

---

## 4. Migration phases (expand / contract)

CLAUDE.md §6 mandates expand/contract for column drops. Each phase = one PR.

### Phase E1 — Add the new tables (additive, zero-risk)

**Alembic migration**: `YYYYMMDD_HHMM_add_article_translations.py`

- `CREATE TABLE article_translations(...)` with all columns + indexes
- Add `canonical_locale`, `is_globally_published` to `articles` (default values)
- **Do not modify** existing `*_darija` / `*_fr` columns
- Add `views_count` to articles if not already present (it already is)

**Code**: new SQLModel `ArticleTranslation` added. No reads or writes happen against it yet.

**Risk**: ~zero. New table is empty until E2.

**Rollback**: `DROP TABLE article_translations` + drop the 2 new columns.

### Phase E2 — Backfill (data move, idempotent)

**Script**: `backend/app/scripts/backfill_article_translations.py`

Pseudo-code:

```python
for article in articles:
    # ar-MA row (always)
    upsert(ArticleTranslation,
           article_id=article.id, locale='ar-MA',
           title=article.title_darija,
           excerpt=article.excerpt_darija,
           content=article.content_darija,
           meta_title=article.meta_title,
           meta_description=article.meta_description,
           reading_time_minutes=article.reading_time_minutes,
           word_count=article.word_count,
           status='published' if article.is_published else 'draft',
           published_at=article.published_at,
           source_locale=None,                 # localized from EN RSS
           generation_method='localize',
           ai_provider='claude',
           ai_model='claude-haiku-4-5',
           prompt_version='v3')

    # fr row (only when fields are present)
    if article.content_fr:
        upsert(ArticleTranslation,
               article_id=article.id, locale='fr',
               title=article.title_fr,
               ...,
               status='published' if article.is_published else 'draft',
               source_locale='ar-MA',          # translated from Darija (today's pipeline)
               generation_method='translate',
               ai_provider='claude',
               ai_model='claude-haiku-4-5',
               prompt_version='v1')

    # Spine
    update(article, canonical_locale='ar-MA',
                    is_globally_published=article.is_published)
```

Run twice to verify idempotency. `--dry-run` flag mandatory.

**Risk**: low. UPSERT on `(article_id, locale)` is safe to re-run.

**Rollback**: `TRUNCATE article_translations` — old data is still in place on `articles`.

### Phase E3 — Dual write (new code path appears, old still primary)

**Pipeline change**: `article_processor._persist_draft()` writes BOTH:

- The legacy columns on `articles` (unchanged)
- `article_translations` rows for each produced locale

**API**: unchanged. Reads still come from the old columns. The feature flag `READ_FROM_TRANSLATIONS_TABLE` defaults `false`.

**Risk**: medium. Bugs in the new write path are invisible until E4.

**Mitigation**: unit tests on `_persist_draft` for both paths; integration test that processes one article and asserts both representations match.

**Rollback**: revert the dual-write code; old representation untouched.

### Phase E4 — Switch reads (one locale at a time)

Behind the flag, public API + admin API + frontend start reading from `article_translations` for **listing pages only first** (lower blast radius than detail pages). Verify on staging-like env.

Then enable for detail pages.

**Risk**: medium-high. Wrong JOIN or wrong filter would surface as missing articles.

**Mitigation**:

- Canary deploy: flag on for 10% of traffic via env var per-pod (not feasible single-node; use shadow read instead)
- **Shadow read**: read from BOTH, compare, log mismatches, return old representation. Run for 24-48 h before the flag flip.
- Hreflang `<link rel="alternate">` tags now sourced from `article_translations.locale` set.

**Rollback**: flip the flag back. Both representations still co-exist.

### Phase C1 — Stop dual write, archive legacy columns

After 7+ days of clean reads from the new table:

- Pipeline stops writing the old columns. Triple-check no reader still consumes them.
- Old columns kept in the DB but unused.

**Risk**: medium. A consumer we forgot continues reading stale data silently.

**Mitigation**: ripgrep audit on `title_darija`, `content_fr`, etc. before the PR. Each remaining call site must be moved or explicitly justified.

**Rollback**: re-enable dual write.

### Phase C2 — Drop legacy columns

After another 7+ days of stable C1:

- Alembic migration: `DROP COLUMN title_darija`, `content_darija`, etc.
- `Article` SQLModel cleaned up.

**Risk**: irreversible without a backup restore.

**Mitigation**:

- Take an explicit `pg_dump` of the `articles` table the morning of the drop.
- The migration is reviewed by the on-call (Yassine) before merge.
- C1 must have been stable in prod for ≥ 7 days with zero incidents.

**Rollback**: restore from the pg_dump taken minutes before. Re-add columns and re-backfill from `article_translations` (the data lives there).

---

## 5. Application-layer changes (overview, not exhaustive)

### Backend

| Layer | Change |
|---|---|
| `app/models/article.py` | Article slimmed; new `ArticleTranslation` model |
| `app/schemas/` | New `ArticleTranslationOut`; `ArticlePublic`/`ArticlePublicDetail` reshape to embed a translation |
| `app/api/v1/articles.py` | `list_public_articles(lang: str)` becomes JOIN-based; `get_public_article(slug, lang)` selects the right translation row |
| `app/api/v1/admin/articles.py` | New endpoints for per-locale status transitions; `PATCH /articles/{id}/translations/{locale}` |
| `app/services/pipeline/article_processor.py` | `_persist_draft` writes translations; signals shift from "publish article" to "publish translation" |
| `app/services/ai/translator.py` | Returned struct lands in `article_translations` (no behaviour change inside the service) |
| `app/scripts/backfill_french_translations.py` | Either removed (no longer relevant — there are no missing French translations after migration) or rewritten to backfill new translations into the new table |

### Frontend

| Layer | Change |
|---|---|
| `app/[locale]/articles/[slug]/page.tsx` | Query takes `locale` + `slug` → server resolves the matching translation; falls back to canonical_locale gracefully |
| `app/[locale]/articles/page.tsx` | Listing already takes `?lang=` — pivots to filter on translation status |
| Admin tabs | Locale tabs already exist (Darija / Français) — they now drive a per-locale status badge |
| Hreflang in `<head>` | Read from server data: `{translations.map(t => <link rel="alternate" hreflang={t.locale} ...>)}` |

### Sitemap / RSS

Sitemap currently lists each article once. After migration, list each `(article, locale)` pair where `status='published'` with `<xhtml:link hreflang>` siblings.

---

## 6. Risk register

| # | Risk | Probability | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Backfill mis-maps a column → wrong content under wrong locale | Low | High (visible to users) | Diff check after E2: per-article SHA256 of old vs new content must match | migration PR author |
| R2 | Dual-write window leaves the two representations divergent | Medium | High | Periodic SHA256 diff job during E3; nightly Slack/Sentry alert on mismatch | migration PR author |
| R3 | Hot read path slows down (JOIN cost) at the 10k+ articles scale | Medium | Medium | Indexes specified upfront; `EXPLAIN ANALYZE` before E4 flag flip; consider denormalized read view if p95 regresses > 30% | DBA / Yassine |
| R4 | `ON DELETE CASCADE` on translations triggers accidental data loss when an article is hard-deleted | Low | High | Soft-delete is the only delete path in the codebase; verify no `DELETE FROM articles` is used; lock down via repo policy | code review |
| R5 | Hreflang regression hurts SEO during the cutover | Medium | Medium | Shadow render in E4 compares old vs new `<link rel="alternate">` set per page | Yassine |
| R6 | Admin UI regression: editor publishes one locale and the other gets unintentionally archived | Medium | Medium | Per-locale UI states with confirmation; admin acceptance test for the 4-state matrix (draft/review/published/archived × 2 locales) | frontend PR |
| R7 | Migration runs against prod without a fresh backup | Low | Catastrophic | C2 PR template includes a backup verification line that CI checks for | release |
| R8 | Alembic `downgrade()` for E1 is broken | Medium | Medium | Every migration tested with `alembic downgrade -1` in CI | CI gate |
| R9 | Backfill script crashes mid-run leaving partial state | Low | Low | Idempotent UPSERT; script can be re-run safely | migration PR author |
| R10 | Tags/categories edited on one translation get out of sync with the article spine | High | Low | Make this an admin UI design rule: tags/categories edit only on the spine (one place); document in admin help | UX |
| R11 | The `prompt_version` we record now becomes wrong when we later refine a prompt | Low | Low | `prompt_version` reflects what the row was generated with — never updated retroactively. This is the desired behavior (immutable provenance) | n/a |
| R12 | Production migration window collides with active editorial work | Medium | Low | Coordinate; migrations are small (50 articles) and fast; expand-phase additive migrations can run anytime | calendar |

---

## 7. Calendar estimate

Conservative, with normal interruptions:

| Phase | Effort | Calendar | Gating |
|---|---|---|---|
| Phase 0 (this fix) | 1-2 days | Now | none |
| Phase 0 in prod + observability | — | 7 days observation | calendar |
| Pre-conditions checklist | 1 day | + 1 day | manual |
| E1 add tables | 0.5 day | + 0.5 day | review |
| E2 backfill | 0.5 day | + 0.5 day | review |
| E3 dual write | 1.5 days | + 1.5 days | review + smoke |
| E4 switch reads (shadow + flip) | 2 days | + 3 days (incl 24-48h shadow) | observation |
| C1 stop dual write | 0.5 day | + 7 days observation | observation |
| C2 drop legacy columns | 0.5 day | + 0.5 day | final review |
| **Total** | **~7-8 dev days** | **~3 weeks calendar** | |

The calendar is dominated by deliberate observation windows, not coding.

---

## 8. Open questions (to resolve before E1)

1. **Slug per article or per translation?** Plan keeps one slug per article (shared across locales). Confirm: is `/fr/articles/openai-raises-40b` acceptable, or should it become `/fr/articles/openai-leve-40-milliards`? **Recommendation**: keep shared slug — slug is in English already, locales discriminate at the URL prefix.
2. **`canonical_locale` value at migration time?** All current rows = `'ar-MA'`. Future Localizer-FR-direct articles would set canonical to `'en'`. **Recommendation**: default to `'ar-MA'` at backfill; pipeline can override later.
3. **Pricing-model rollover**: should `ai_model` on translations be free text or FK to a `models` table? **Recommendation**: free text for now. Adding a `models` table is YAGNI at this scale.
4. **Admin endpoint shape**: `PATCH /articles/{id}/translations/{locale}` or `PATCH /article_translations/{id}`? **Recommendation**: scoped form (`/articles/{id}/translations/{locale}`) — matches how the admin UI thinks ("edit French of article 47").
5. **Hard delete vs archive on translations**: should the admin ever truly delete a translation row? **Recommendation**: no. `status='archived'` and re-running the pipeline overwrites the row.

These need decisions from Yassine before E1 ships.

---

## 9. Non-goals to call out explicitly

- This migration does NOT switch FR away from Darija→FR. It enables that choice as a code/config change later.
- This migration does NOT add MSA/EN/ES. It makes adding them trivial.
- This migration does NOT change any prompt.
- This migration does NOT change the editorial workflow other than adding per-locale status (which is opt-in: status can be left at 'draft' indefinitely; existing behavior preserved).
- This migration does NOT touch admin auth, CORS, rate limiting, RSS ingestion, image generation pipeline, or social posts.

---

## 10. Sign-off required before E1

- [ ] Yassine reviewed § 3 (schema), § 4 (phases), § 6 (risks)
- [ ] Yassine answered § 8 open questions
- [ ] `ai_logs` populated in prod for ≥ 7 days
- [ ] Backup/restore procedure tested
- [ ] Backend test coverage on `app/models/article.py` ≥ 80%
- [ ] This document committed to `main`
