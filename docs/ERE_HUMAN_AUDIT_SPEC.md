# ERE Human Audit V1 — Specification

## Goal
Let an admin review ERE **shadow** decisions and record a human verdict (KEEP / REJECT),
to measure precision/recall. **No** auto-publish, **no** ranking change, **no** ERE score /
`editorial_decision` / `processing_status` modification. The verdict lives in its own table.

## Architecture note
This adds the **first write-path** to the ERE admin area: a `POST` that writes ONLY into the
new `editorial_audits` table, fully decoupled from `raw_articles`/ERE. The dashboard stays
read-only with respect to ERE and publication.

## Approved decisions
- **D1** — one verdict per article: `UNIQUE(article_id)` + **upsert** (re-audit overwrites, bumps `updated_at`).
- **D2** — queue order: **borderline-first** `ABS(editorial_score - 55) ASC` (score-desc optional later).
- **D3** — FK: `article_id REFERENCES raw_articles(id) ON DELETE CASCADE`.
- **D4** — reviewer: taken from the authenticated admin JWT email (no free-text field).
- **D5** — write path approved; KEEP/REJECT buttons allowed; the ONLY write is into `editorial_audits`. No publish/enforce/ranking/score change.

## Data model — `editorial_audits`
| col | type | notes |
|--|--|--|
| id | bigserial PK | |
| article_id | int NOT NULL FK→raw_articles(id) ON DELETE CASCADE, UNIQUE | one verdict/article |
| ere_score | smallint NOT NULL | snapshot at audit time |
| ere_decision | varchar(12) NOT NULL | snapshot (selected/deferred) |
| human_verdict | varchar(8) NOT NULL CHECK IN ('KEEP','REJECT') | |
| reviewer | varchar(255) NOT NULL | admin JWT email |
| notes | text NULL | |
| created_at | timestamptz NOT NULL default now() | |
| updated_at | timestamptz NOT NULL default now() | bumped on upsert |

Indexes: `human_verdict`, `ere_decision`. Migration `down_revision = c3f8a1e6b4d9`.

## Metrics (computed purely from `editorial_audits`, no join)
| | human KEEP | human REJECT |
|--|--|--|
| ere selected | TP | **FP** |
| ere deferred | **FN** | TN |

`precision = TP/(TP+FP)` · `recall = TP/(TP+FN)` · `audited = total rows`.

## API — under `/api/v1/admin/ere` (admin-auth)
- `GET /audit/queue?limit=&cursor=` — scored articles NOT yet audited
  (`LEFT JOIN editorial_audits … WHERE a.id IS NULL`), ordered borderline-first; returns
  `{ data:[{id,title,source,score,decision,category,breakdown}], next_cursor }`.
- `POST /audit/verdict` — body `{article_id, human_verdict, notes?}`. Snapshots ere_score/
  decision from `raw_articles` (404 if missing/unscored), reviewer = JWT email, **upsert** on
  `article_id`. 422 on invalid verdict. Returns the audit record.
- `GET /audit/metrics` — `{audited, tp, fp, fn, tn, precision, recall}`.

## Frontend — "Human Audit" section in `/admin/ere`
Metrics cards (audited / precision / recall / false positives / false negatives) + a review
card (title, source, ERE score, decision, strategic category, score breakdown, notes field,
**KEEP / REJECT** buttons). `useMutation` POSTs the verdict, then invalidates queue+metrics.
No publish/pause/enforce buttons. CSS/SVG, no new dependency.

## Tests
Migration up/down; auth-required; queue excludes audited + borderline-first; POST creates;
POST upsert; POST snapshots ere_score/decision; POST leaves raw_articles
score/decision/processing_status unchanged; metrics TP/FP/FN/TN + precision/recall; frontend build.

## Rollback
Revert PR → redeploy without the feature; `alembic downgrade c3f8a1e6b4d9` drops
`editorial_audits` (only the audit rows are lost). No impact on ERE/ranking/publication.
