# Localizer A/B/D/E comparison — 2026-05-04

Test subject: `raw_articles.id = 4` — *"Salesforce rolls out new Slackbot AI agent as it battles Microsoft and Google in workplace AI"* (VentureBeat AI, ~15.7 KB / ~2400 EN words).

System prompt: `localizer_v1.md` (v1.2, with anti-translation patterns).

## Comparison

| Mode | Models | Cost | Duration | Words | Defects | QC | File |
|---|---|---:|---:|---:|---:|---|---|
| **A: Haiku-only** | `claude-haiku-4-5` | **$0.0416** | 364 s¹ | 1111 | n/a | passed (2 warn) | [`mode_A_haiku.md`](./mode_A_haiku.md) |
| B: Sonnet-only | `claude-sonnet-4-6` | $0.1107 | 89 s | 866 | n/a | passed (2 warn) | [`mode_B_sonnet.md`](./mode_B_sonnet.md) |
| D: Cross-model | `claude-haiku-4-5` → `gpt-4o-mini` → `claude-haiku-4-5` | $0.0719 | 190 s | 1050 | 6 | passed (2 warn) | [`mode_D_cross_model.md`](./mode_D_cross_model.md) |
| E: OpenAI sanity | `gpt-4o-mini` × 3 | $0.0044 | 74 s | 406 | 4 | passed (1 warn) — *not for Darija quality* | [`mode_E_openai_sanity.md`](./mode_E_openai_sanity.md) |

¹ Mode A duration includes one mid-run `httpx.ReadTimeout` retry; absent the retry, Haiku typically finishes the same input in ~60–90 s.

## Findings

- **Quality (qualitative, by native review)**:
  - A — good but with translated patterns (~10–15% rough patches)
  - B — excellent, native Moroccan flow
  - D — comparable to B; GPT critic correctly flagged 6 valid defects (3× English filler, 1× quote framing, 1× generic takeaway, 1× structural). Haiku rewriter applied all 6 plus 3 more it caught itself.
  - E — mechanically validated only; GPT writes weak Darija (MSA-leaning).
- **Risk in cross-model**: GPT-4o-mini occasionally emitted **reverse-RTL Arabic** in `suggested_fix` payloads (e.g. `'يكذ ليكو'` instead of `'وكيل ذكي'`). The Haiku rewriter caught and ignored the bad suggestion in this run, but the failure mode is non-deterministic at scale.
- **Cross-family critique works in principle**: GPT-4o-mini caught real issues that an in-family critic would likely gloss over (English-filler nouns, missing quote framing). Worth revisiting once GPT's RTL behavior stabilizes.

## Decision (ADR-002, see `docs/DECISIONS.md`)

**Production: Mode A — `claude-haiku-4-5` single-pass — with mandatory human review** in the admin panel before publication. Articles are saved as drafts (`is_published=False`); the editor (a Moroccan native speaker) reviews and clicks "Publish".

Rationale highlights:
1. Volume is 3–4 articles/day. Editor reads the article either way; first-draft model quality isn't the binding constraint.
2. Human-in-the-loop is the editorial QA layer.
3. Sonnet 4.6 stays opt-in via Localizer's `model` parameter for flagship pieces.
4. Cross-model code preserved (`app/services/ai/cross_model_pipeline.py`) for re-evaluation when GPT's RTL behavior is fixed.

**Cost @ 4 articles/day: ~$5/month.**

## Reproducing

```bash
cd backend
.venv/Scripts/python.exe -m app.scripts.process_article --article-id 4 --mode haiku-only
.venv/Scripts/python.exe -m app.scripts.process_article --article-id 4 --mode sonnet-only
.venv/Scripts/python.exe -m app.scripts.process_article --article-id 4 --mode cross-model
.venv/Scripts/python.exe -m app.scripts.process_article --article-id 4 --mode openai-only
```

Each run writes its output to `backend/logs/localized_<id>_<mode>.md` (gitignored). The four files in this directory are the snapshot of the 2026-05-04 comparison.
