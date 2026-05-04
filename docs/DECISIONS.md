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
