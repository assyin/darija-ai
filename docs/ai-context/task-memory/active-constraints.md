# Active Constraints

> Update: when a constraint is added, lifted, or changes scope.
> Rule: only constraints that actively affect code decisions RIGHT NOW. Permanent rules live in CLAUDE.md.
> If a constraint is in CLAUDE.md already, do NOT duplicate it here.

---

## Hard technical constraints (affect every code decision)

| Constraint | Impact | Source |
|---|---|---|
| Claude for Arabic only — no GPT | Never use GPT for localization or Arabic content | ADR-002, validated |
| `is_published=False` always on AI output | Every generated article is a draft. No auto-publish path. | Product rule |
| Quality gate must pass before any publish | 6 checks. Cannot be skipped "just this once". | CLAUDE.md §5 |
| `localizer_v1.md` is now effectively frozen | Any further prompt changes must be `localizer_v2.md` | Prompt versioning rule |
| No auth on admin routes yet (REFACTOR-03) | Admin API is currently open. Do not expose publicly. | Known gap |

---

## Current external constraints (time-bound or situational)

| Constraint | Expires / Changes when | Impact |
|---|---|---|
| Solo founder — no team review | Until first collaborator | PRs still required; self-review only |
| $50/mo infra budget cap | Hard cap — no expiry | Every new service needs cost justification |
| No CI/CD pipeline yet | Until `.github/workflows/` is built | All checks must be run manually before commit: `make check` |
| Frontend not connected to real API | Until REFACTOR-02 is done | Frontend changes are UI-only for now |
| All features are pre-staging | Until Railway staging env is provisioned | Test against local Docker only |

---

## Things that are NOT constraints (common misconceptions)

- **Sonnet 4.6 is NOT blocked** — it's opt-in for flagship articles via `model=` param.
- **The cross-model pipeline is NOT deleted** — it's preserved, just excluded from context by `.claudeignore`.
- **`mypy --strict` applies to backend only** — frontend uses TypeScript strict, not mypy.
- **Distribution is NOT blocked by auth** — it's just not built yet. They're independent tracks.

---

## Context budget (current session)

> Quick reference — see session-reset-strategy.md for full rules.

| Loaded so far | Approx tokens |
|---|---|
| CLAUDE.md (auto) | ~2,900 |
| current-focus.md | ~400 |
| recent-decisions.md | ~500 |
| implementation-status.md | ~900 |
| pending-refactors.md | ~700 |
| active-constraints.md | ~450 (this file) |
| **Total (memory system only)** | **~5,850** |

If loading this full memory set + 2 domain files + 3 code files: ~10,000–14,000 tokens. Well under the 50K session budget.

---

*Last updated: 2026-05-06*
