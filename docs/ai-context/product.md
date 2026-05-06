# Product Context — DarijaAI

> Load this file when: product decisions, editorial rules, user-facing copy, feature scoping.

---

## What this is

**DarijaAI** — Moroccan Darija AI/tech news platform. The first editorial-grade media in Darija for the Maghreb tech community.

**NOT** a translation service. Content is editorially localized — native voice, not literal translation.
**NOT** a general news site — AI/tech only, deep specialization.
**NOT** fully automated — human editorial review is mandatory before publication.

## Editorial workflow (sacred)

```
RSS scrape → AI localize (Haiku) → Image gen → Draft saved → Owner reviews → Publish → Distribute
```

- All AI output is `is_published=False` (draft) until owner approves in admin panel.
- Owner = Moroccan native Darija speaker. The human review IS the QA layer.
- "Publish" button in admin UI is the only thing that flips `is_published=True`.

## Target audience

Moroccan and Maghrebi tech community. ~70% mobile traffic. RTL is the primary rendering mode.

## Success metrics (Month 1)

- 5,000 unique visitors
- 200+ indexed articles
- Lighthouse ≥95 perf/SEO
- Infra cost ≤$50/mo
- Zero incidents >10 min

## Budget constraint

$50/month hard cap on infrastructure. AI calls must be cache-first. Every dependency has a cost.

## Content rules

- Darija strings are never auto-edited by AI assistants. System prompt produces them; owner validates them.
- Glossary in `darija_glossary` DB table is canonical for technical terms.
- 3–4 articles/day target volume.
