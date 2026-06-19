# SpendGuard V2 — Budget vs Emergency pause

## Why
V1 used a single sticky flag (`ai:paused`, no TTL) for two unrelated causes:
- **budget** (daily cap reached) — soft, recurring, expected;
- **emergency** (billing/quota failure) — hard failure.

The sticky behaviour is correct for the emergency case ("never auto-resume into
a dead account", 2026-06-08 RCA) but forced **daily operator toil** on the
budget case, and there was **no monthly ceiling** even though `$2/day × 30 =
$60 > $50/mo` (CLAUDE.md §1).

## Design
Two distinct Redis keys, evaluated in `SpendGuard.allow()` before every article:

| Key | Cause | Lifetime | Resume |
|--|--|--|--|
| `ai:paused:budget` | `daily_cap_reached` | **TTL = until next UTC midnight** | **auto** |
| `ai:paused:emergency` | `billing_error`, `monthly_cap_reached`, operator | **no TTL (sticky)** | **manual** |
| `ai:paused` (legacy V1) | any | no TTL | honoured as emergency until cleared |

`allow()` order: emergency → budget → **monthly cap (→ emergency)** → daily cap
(→ budget) → allow. The monthly guardrail uses the existing (previously
unenforced) `settings.ai_monthly_cap_usd = $50`, summed over the calendar month
from `ai_logs`. The daily hard cap (`$2`) is unchanged.

## Preserved safety guarantees
- Billing/quota error → **sticky** emergency pause, manual resume only (V1 parity).
- Monthly spend ≥ `$50` → **sticky** emergency pause — autonomy can never breach
  the monthly ceiling even though daily caps alone would allow `$60/mo`.
- Daily cap still enforced (`$2/day`); the only change is that the *budget* pause
  auto-resumes at midnight instead of requiring manual intervention.
- No auto-resume for any emergency cause.

## Migration (no DB change)
SpendGuard V2 is **Redis-state only — there is no Alembic/DB migration** (the
monthly sum reuses the existing `ai_logs` table). The transition is handled by
**backward compatibility**: V2 honours the legacy `ai:paused` key as an
emergency pause, so deploying V2 to a currently-paused production **keeps it
paused exactly as-is** (no silent unpause). When ready, the operator runs the
normal resume — `python -m app.scripts.resume_ai_processing` — which now clears
**all three** keys, completing the transition. From then on, budget pauses
auto-resume and emergencies stay sticky.

## Rollback
Revert the PR. Caveat: V1 only reads `ai:paused`. If, at revert time, a pause is
held by a **V2-only** key (`ai:paused:budget` / `ai:paused:emergency`), reverting
to V1 would ignore it and could unpause. **Before reverting while paused**, set
the legacy key so V1 keeps the pause:
`redis-cli SET ai:paused '{"reason":"rollback_hold"}'`. Then revert.

## Operability
- Status (read-only): `python -m app.scripts.ai_spend_status` — shows daily +
  monthly spend, caps, and each pause flag (emergency / budget / legacy).
- Resume (manual): `python -m app.scripts.resume_ai_processing` — clears all
  pauses; warns if today's or this month's spend will immediately re-trip.

## Not in scope
No change to the soft `$5/day` Sentry alert (`check_daily_ai_spend`), no change
to the daily cap value, no enforce/automation beyond the existing gate, no deploy.
