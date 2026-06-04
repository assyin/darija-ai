# Architecture Decisions

## ADR-001: Keep MIN_WORD_COUNT at 200 in relevance_filter

**Date**: 2026-05-03
**Status**: Accepted
**Context**:
RSS feeds vary wildly in content depth. VentureBeat ships full articles in
<content:encoded>; TechCrunch and Hugging Face Blog ship 80-150 word teasers.
With MIN_WORD_COUNT=200, only VentureBeat clears the filter on first ingestion.

**Decision**:
Keep the threshold at 200 words. Articles below this are too thin to produce
editorially valuable Darija localizations and would waste Claude API tokens
on low-quality input. The right fix is to enrich short RSS summaries by
fetching the full article from `entry.link` with selectolax (planned: HTML
enrichment service, post-MVP).

**Consequences**:
- Initial article volume is lower (1 source out of 4 active feeds)
- Quality of ingested articles is preserved
- Diversification deferred until HTML enrichment is implemented

**Alternatives considered**:
- Lower threshold to 100: would let through teasers that produce poor translations
- Per-source thresholds: adds config surface; better to fix at the data layer

---

## ADR-002: Haiku 4.5 single-pass + mandatory human review

**Date**: 2026-05-04
**Status**: Accepted
**Context**:
We A/B/D/E-tested four localization configurations on real article #4 (Salesforce
Slackbot, ~1000 EN words):

| Mode | Models | Cost | Duration | Words | Quality (qualitative) |
|---|---|---:|---:|---:|---|
| A | Haiku-only (`claude-haiku-4-5`) | $0.041 | 364 s | 1111 | good, but with translated patterns |
| B | Sonnet-only (`claude-sonnet-4-6`) | $0.111 | 89 s | 866 | excellent, native Moroccan flow |
| D | Cross-model: Haiku → GPT-4o-mini critic → Haiku rewriter | $0.072 | 190 s | 1050 | comparable to Sonnet; critic flagged 6 valid defects, rewriter applied 9 corrections |
| E | GPT-4o-mini × 3 (sanity check only) | $0.004 | 74 s | 406 | mechanically validated; Darija quality weak (MSA-leaning) |

Mode D revealed a non-deterministic risk: **GPT-4o-mini occasionally produced
reverse-RTL Arabic in `suggested_fix` payloads** (e.g. `'يكذ ليكو'` instead of
`'وكيل ذكي'`). On this run the Haiku rewriter caught and ignored the bad
suggestion, but the risk is real at scale.

**Decision**: **Haiku 4.5 single-pass for production**, with **mandatory human
review** before publication. The project owner (a Moroccan native speaker)
reviews every article in the admin panel and clicks "Publish" — that is the
editorial QA layer. Articles are persisted as drafts (`is_published=False`);
nothing auto-publishes.

The Localizer's default `model` is `"claude-haiku-4-5"`; the default `--mode`
for `process_article.py` is `haiku-only`. Sonnet remains opt-in for flagship
articles by passing `model="claude-sonnet-4-6"`.

**Rationale**:
1. **Volume is small.** 3–4 articles/day. Annual cost vs Sonnet: ~$60 vs ~$156
   — savings are real but not the headline argument.
2. **Human-in-the-loop is the QA layer.** Haiku produces good-but-imperfect
   Darija (~10–15% rough patches per Mode A test). The owner catches these in
   review. The design does **not** rely on the model alone for quality.
3. **System prompt v1.2** addresses the most common failure modes
   (anti-translation patterns, English filler list, takeaway specificity),
   reducing the manual cleanup the editor must do.
4. **Sonnet is opt-in, not removed**, for flagship pieces where the editor
   wants a cleaner first draft.
5. **Cross-model code preserved** in `cross_model_pipeline.py` and
   `prompts/critic_v1.md` / `prompts/rewriter_v1.md` for re-evaluation if
   GPT's RTL behavior is fixed.

**Workflow**:

```
RSS scraper
   → Localizer (Haiku)
   → Image generator
   → Article saved as DRAFT (is_published=False)
   → Human reviewer in admin panel
   → "Publish" button → distribution triggered
```

**Consequences**:
- Default production model is Haiku 4.5; the editor's manual review is a hard
  prerequisite before publication.
- `app/services/ai/cross_model_pipeline.py` and `app/services/ai/openai_client.py`
  remain in the repo as opt-in tools (CLI: `--mode cross-model` or
  `--mode openai-only`), not on any production path.
- If Anthropic ships a Haiku successor with materially better Darija, revisit.

**Alternatives considered**:
- Mode B (Sonnet): higher quality first draft, but adds ~$96/year and the human
  reviewer needs to read the article anyway — model quality is not the binding
  constraint at our volume.
- Mode D (cross-model): potentially equal/better than Sonnet, but introduces
  GPT RTL hallucination risk and a second-provider dependency; not worth it
  while the editor is in the loop.
- Mode E (GPT-only): not a serious candidate; included only as a pipeline
  mechanics sanity test.

**Cost estimate**: ~$5/month at 4 articles/day (~$60/year).

**Validation artifacts**: `docs/test-results/2026-05-04-localizer-comparison/`.

---

## ADR-003: Normalize multilingual content into `article_translations`

**Date**: 2026-06-04
**Status**: ✅ Accepted (design only — execution deferred behind ai_logs fix)
**Authors**: Yassine (CTO), Claude (advisor)
**Supersedes**: schema choices implicit in migration `7f3a9c2e1b8d_add_french_columns_to_articles`

### Context

TitritAI launched bilingual (Darija + French) by adding sibling columns to the
`articles` table: `title_darija/content_darija/...` alongside `title_fr/
content_fr/...`. Migration `7f3a9c2e1b8d` introduced the FR columns; PR #17
wired auto-translation into the pipeline.

The roadmap targets **5 locales over 2 years**: ar-MA (Darija), fr, ar (MSA),
en, es. Continuing the sibling-columns pattern would mean **~25 sparse text
columns** on a single table by 2028 (5 locales × 5 text fields), with no
per-locale publication state, no provenance metadata, and a structural
inability to express common editorial workflows (e.g. "Darija published,
French in review").

The full 2026-06-04 architectural analysis is in this conversation log and
referenced from `docs/ai-context/`.

### Decision

Replace the sibling columns with a **normalized `article_translations`
table**, one row per `(article_id, locale)` pair. The parent `articles` row
holds only language-agnostic data: slug, hero image, categories, tags, source
provenance (`raw_article_id`).

```text
articles                 (language-agnostic spine)
   └── id, slug, raw_article_id, hero_image_url, hero_image_alt,
       categories[], tags[], canonical_locale, is_globally_published,
       created_at, updated_at, deleted_at

article_translations     (per-locale payload, status, provenance)
   └── id, article_id (FK), locale, title, excerpt, content,
       meta_title, meta_description, reading_time_minutes, word_count,
       status ('draft'|'review'|'published'|'archived'),
       published_at, human_reviewed_at, human_reviewer_id,
       source_locale, generation_method, ai_provider, ai_model,
       prompt_version, created_at, updated_at
       UNIQUE (article_id, locale)
```

### Rationale

| Outcome | How the new schema delivers |
|---|---|
| Add a new locale = INSERT, not migration | New rows in `article_translations`; no DDL touching the hot `articles` table |
| Per-locale publication state | `article_translations.status` is independent for each row |
| SEO `hreflang` becomes a SELECT | `SELECT locale FROM article_translations WHERE article_id=X AND status='published'` |
| Cost attribution per translation | `(ai_provider, ai_model, prompt_version)` columns join cleanly to `ai_logs` |
| Provenance honesty | `source_locale` records whether this is a direct localization (NULL/'en') or a translation from another locale ('ar-MA') |
| `/fr/articles` listing | One indexed predicate: `WHERE locale='fr' AND status='published'` |
| Translator/Localizer can be swapped per locale | `generation_method + prompt_version` describe HOW each row was produced — A/B testing strategies becomes data-level, not code-fork-level |

### Alternatives considered

**A. Status quo (sibling columns)**: Rejected — does not scale to 5 locales,
forces every new locale into a migration, no per-locale status, no
provenance.

**B. JSONB `translations` column on `articles`**: Rejected — loses indexing
on title/content, complicates per-locale queries, makes status enforcement a
CHECK constraint over JSONB paths (fragile). Postgres JSONB is great for
schema-less metadata, not for editorial content with strong invariants.

**C. Separate table per locale (`articles_fr`, `articles_ar`…)**: Rejected —
explodes table count, breaks DRY for indexes/policies/triggers, every new
locale is still a migration. Worst of both worlds.

**D. Move articles into a CMS (Strapi, Sanity, Directus)**: Out of scope.
The editorial pipeline is custom for Darija specifics; a generic CMS would
require re-implementing the AI pipeline glue. Reconsider only if editorial
team grows past 1 reviewer.

### Consequences

**Positive**:
- One-time migration cost; permanent scaling capability
- Smaller `articles` row → better cache hit on hot read paths
- Each translation owns its lifecycle → editorial flexibility
- ai_logs becomes joinable to specific translations via `prompt_version`
- Foundation for the Option B (independent per-locale localization)
  recommended in the Phase 1+ roadmap, **without** committing to it now

**Negative**:
- Every read path that touches translated content needs a JOIN
- Backend services and frontend types both change shape (DTO surface grows)
- Two-phase expand/contract migration takes calendar time (per CLAUDE.md §6
  policy: never `DROP COLUMN` directly)
- 50 existing articles need backfill (trivial at this volume; mandatory)

### Scope boundaries

This ADR is about the **schema**. It does NOT decide:
- Whether FR remains Darija→FR (Option A) or moves to EN→FR (Option B) — that
  becomes a per-locale config in the new schema
- When other locales (ar, en, es) ship — separate product decisions
- Admin UI shape — driven by the schema but designed separately

### Pre-conditions

1. **`ai_logs` cost tracking must be fixed first** (RCA 2026-06-04). Without
   per-call cost data, decisions made after the migration are blind. The
   migration plan explicitly depends on this.
2. Backend test coverage on `Article` model paths >= 80% (CLAUDE.md §8) —
   current state should be re-measured before migration starts.
3. Schema migration plan (`docs/migrations/2026-06-04-article-translations.md`)
   accepted by Yassine.

### Verification (post-migration)

- All 50 existing articles render identically at `/articles/<slug>` and
  `/fr/articles/<slug>` (HTML diff before/after expected to be a no-op
  for content; minor DOM changes around metadata acceptable)
- `pg_stat_statements` shows no new slow queries above the p95 baseline
- ai_logs join to `article_translations` resolves cleanly:
  `SELECT t.locale, SUM(l.cost_usd) FROM ai_logs l JOIN article_translations t USING (prompt_version) GROUP BY 1` returns sane numbers
- Per-locale publish workflow is exercised once end-to-end in admin UI
