# Current Focus

> Update: every session start and end. This is the first file to load.
> Rule: only ONE active focus at a time. Everything else goes to implementation-status.md.

---

## Active task

**P0-A (Worker) + P0-B (Admin wiring) both DONE (2026-05-25). Next: P1-C quick fixes, then P0-C CI/CD.**

- **P0-A** committed `3da42a5` (branch `feat/worker-scheduler`): arq jobs + cron scheduler.
- **P0-B** done (D2 = NextAuth httpOnly session + same-origin authed proxy). Login→list→edit→publish verified E2E via curl. tsc + eslint clean.

Next per `PROD-IMPLEMENTATION-PLAN.md`:
- **P1-C** quick fixes (can start now): FIX-M1/M2/M3, FIX-S1/S4/S5, backend password hashing, public rate limiting.
- **P0-C** CI/CD + envs (GitHub Actions, Railway/Vercel/Neon/Upstash/R2, staging).
- Remaining admin gap: sources page needs a backend `/admin/sources` endpoint (separate task).

## Files actively modified (unstaged)

P0-B (not yet committed): `frontend/lib/auth.ts`, `frontend/types/next-auth.d.ts`, `frontend/app/(admin)/login/page.tsx`, `frontend/lib/api-client.ts`, `frontend/app/api/admin/[...path]/route.ts`, `frontend/app/(admin)/admin/{articles/page,articles/[id]/page,settings/page}.tsx`.

## Next concrete action

1. Commit P0-B as `feat(admin): wire admin panel to backend via authed proxy`.
2. Start P1-C quick fixes (independent, fast wins).

## Blocked on

- Nothing blocking. P0-C needs cloud account/secrets access (Railway, Vercel, Neon, Upstash, R2, GitHub secrets).

---

*Last updated: 2026-05-25*
