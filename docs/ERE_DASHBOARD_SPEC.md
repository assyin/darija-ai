# ERE v1.1 Dashboard — Specification (read-only observability)

## Goal & constraints
Admin-only, **100% read-only** observability dashboard for the ERE v1.1 shadow data, to
validate ranking quality / threshold / categories / sources **before** any enforce or
auto-publish discussion. No ranking-logic change, no publication action, no jobs, no config
change, no new dependency, CSS/SVG charts only.

Data sources (read-only): `raw_articles` (`editorial_score` / `editorial_decision` /
`score_breakdown` JSONB), `ai_logs` (spend), Redis SpendGuard keys, settings (caps/flags).
The "scored" set everywhere = `WHERE editorial_score IS NOT NULL`.

## Derived strategic category
```
strategic_label != 'none'              → that label
strategic_label = 'none' AND actors>0  → 'actors_only'
else                                   → 'none'
```
Labels: `frontier_move | market_structure | infra_standards | enterprise_labor |
sovereignty_policy | actors_only | none`.

## Sections (10 + Coming Soon)
1. **Executive Overview** — total scored, selected/deferred count+%, avg/max/min score, last computed_at, model `v1_1`.
2. **Score Distribution** — 5-pt histogram (0-100) + editorial buckets (0-20/21-40/41-54/55-69/70-84/85-100), threshold 55 marker.
3. **Selected Articles** — table (id, title, source, score, decision, category, actors, computed_at) + filters (source, date, score range, category) + sort score↓.
4. **Deferred Articles** — same table, `decision=deferred` (false-negative audit).
5. **Strategic Categories** — per category: count, selected %, avg score (bar chart + table).
6. **Sources Performance** — per source: total, selected, deferred, avg score (detect noisy sources).
7. **Top Selected** — top 25 by score (score, source, title, category).
8. **Borderline Zone** — `50 ≤ score ≤ 60` (id, title, score, decision, category) — calibration candidates.
9. **Shadow Validation** — selected/deferred counts, ratio, avg, distribution by category (reuses §1+§5).
10. **SpendGuard Monitoring** — today/month spend, daily/monthly cap, budget pause, emergency pause, next auto-resume. **Read-only widgets, no control buttons.**
- **Coming Soon (NOT implemented)** — human audit, precision, recall, enforce, auto-publish (disabled placeholders).

## API (GET, admin-auth, read-only) — prefix `/api/v1/admin/ere`
| Endpoint | Sections | Notes |
|--|--|--|
| `GET /overview` | 1, 9 | counts/%, avg/max/min, last_scored, model |
| `GET /distribution` | 2 | histogram bins + editorial buckets |
| `GET /articles` | 3,4,7,8 | filters `decision,source,category,score_min,score_max,date_from,date_to`, sort score↓, keyset cursor, limit |
| `GET /categories` | 5, 9 | per category count / selected_pct / avg_score |
| `GET /sources` | 6 | per source total / selected / deferred / avg_score |
| `GET /spendguard` | 10 | today/month spend, caps, pause states (Redis), next_auto_resume |

Lists return `{ data: [...] }`; errors `{ error: { code, message, request_id } }`. Only GET.
`§7` = `/articles?decision=selected&limit=25`; `§8` = `/articles?score_min=50&score_max=60`.

## Performance note
`score_breakdown` is JSONB without an index on `strategic_label` — fine at current volume
(~150 scored rows). If the scored set grows beyond ~50k, add a GIN index or a read-model
(plan later, not in MVP). `editorial_decision` is already indexed.

## Implementation
- Backend: `services/editorial/dashboard_service.py` (read-only aggregates) +
  `schemas/ere_dashboard.py` + 6 thin GET controllers under `api/v1/admin/ere/`, existing
  admin auth. Tests: auth-required, overview aggregates, articles filtering, categories,
  sources, spendguard (FakeRedis).
- Frontend: admin page `/admin/ere`, RSC fetch for static panels, client components for
  filters/tables/charts (CSS/SVG, no charting dep), Coming Soon placeholders. No action buttons.

## Out of scope (guardrails)
Read-only only · no ranking change · no publication flow · no auto-publish · no enforce · no
SpendGuard control buttons · no background jobs · no config change · no new dependency · no
deploy until PR reviewed.
