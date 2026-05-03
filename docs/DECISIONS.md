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
