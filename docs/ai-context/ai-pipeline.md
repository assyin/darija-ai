# AI Pipeline Context — DarijaAI

> Load this file when: localization, quality gate, prompts, image generation, AI costs, Claude API.

---

## Production pipeline (ADR-002)

```
raw_article → Localizer (Haiku 4.5) → quality_gate() → ImageGenerator (Flux Schnell) → draft article
```

All articles saved as **draft** (`is_published=False`). Human review required before publish.

## Model selection

| Use | Model | How to activate |
|---|---|---|
| Default (all articles) | `claude-haiku-4-5` | Default in `Localizer` |
| Flagship articles | `claude-sonnet-4-6` | Pass `model="claude-sonnet-4-6"` to `Localizer()` |
| Image generation | `black-forest-labs/flux-schnell` | Via Replicate API |
| Cross-model critic | NOT in production | Code preserved, not in prod path |

**Never use GPT for Arabic content.** Claude significantly outperforms on Darija quality.

## Prompt system

- Prompts live in `backend/app/services/ai/prompts/*.md`.
- Versioned filenames: `localizer_v1.md`. **Deployed versions are immutable.**
- New version = new file. Never edit a file that's in production.
- Active version pinned in config: `LOCALIZER_PROMPT_VERSION=v1`.
- `localizer_v1.md` is 52KB — the primary system prompt. Load explicitly only when editing it.

**Prompt engineering log**: `docs/PROMPTS.md` (not yet created — track changes there when it exists).

## Caching (mandatory)

Every Claude call must be cached:
- Key: `sha256(prompt_version + input_content)`
- TTL: 30 days in Redis
- Never hit the API if a cache entry exists.

## Quality gate thresholds (blocks `is_published=True`)

All 6 checks must pass:
1. `langdetect` confidence `ar` > 0.95
2. Word count: 300–1500 words
3. No residual English: no >5 consecutive Latin chars in body (tech terms allowlisted)
4. Structure: ≥2 H2 headings + ≥1 list
5. Glossary: ≥80% of detected tech terms match `darija_glossary` table
6. No placeholders: no `[TODO]`, `lorem ipsum`, `<placeholder>`

If any check fails → `status = "rejected"`, log reason. If rejection rate > 30% → Sentry alert.

## Cost tracking (mandatory)

Every AI call → row in `ai_logs` table:
- Fields: tokens_in, tokens_out, model, cost_usd, article_id, success, error
- Sentry alert if daily total cost > $5

## Image generation

- Always 1024×576 (16:9, for OG images)
- Upload to R2 with hash-based filename (immutable, cached forever)
- Fallback: if Replicate fails 3×, use curated default image per category
- Style: editorial, abstract, blue/purple gradient, no text, no humans

## Non-production code (preserved, not active)

These exist in the codebase but are NOT in the production pipeline (ADR-002):
- `cross_model_pipeline.py` — Haiku → GPT critic → Haiku rewriter
- `openai_client.py` — GPT-4o-mini client
- `critic_editor.py` — Combined critic + editor service
- `prompts/critic_v1.md`, `prompts/critic_editor_v1.md`, `prompts/rewriter_v1.md`

**Do not add these to the production path without updating ADR-002 in `docs/DECISIONS.md`.**

## Key source files

```
backend/app/services/ai/
├── localizer.py          # Main localization service (10KB)
├── claude_client.py      # Anthropic SDK wrapper (6KB)
├── quality_gate.py       # 6-check quality gate (6KB)
├── prompt_loader.py      # Loads .md prompts from disk
├── pricing.py            # Per-model cost calculation
└── bidi.py               # Arabic RTL text direction utilities
backend/app/services/images/
├── image_generator.py    # Orchestrates generation + upload
├── replicate_client.py   # Flux Schnell via Replicate API
└── r2_storage.py         # Cloudflare R2 upload
```
