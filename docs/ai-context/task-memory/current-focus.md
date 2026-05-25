# Current Focus

> Update: every session start and end. This is the first file to load.
> Rule: only ONE active focus at a time. Everything else goes to implementation-status.md.

---

## Active task

**P0-A Worker + Scheduler — DONE (2026-05-25). Next: P0-B Admin câblé (REFACTOR-02 Phase B).**

Roadmap Phase 3 / REFACTOR-01 complete: `ArticleProcessor` service + arq jobs + cron scheduler (D1 = arq-only). Worker boots (4 jobs + 3 cron), 5 integration tests passing, ruff + mypy-strict clean on new modules.

Next per `PROD-IMPLEMENTATION-PLAN.md`:
- **P0-B** — Admin panel API wiring (needs D2: token storage cookie vs localStorage). `frontend/lib/auth.ts` already exists — inspect first.
- In parallel: quick fixes P1-C (FIX-M1/M2/M3, FIX-S1/S4/S5).

## Files actively modified (unstaged)

New (untracked), not yet committed:
- `backend/app/services/pipeline/article_processor.py`
- `backend/app/workers/{__init__,settings}.py` + `backend/app/workers/jobs/{__init__,fetch_articles,process_articles,retry_failed}.py`
- `backend/app/scripts/process_pending.py`
- `backend/tests/integration/test_article_processor.py`
- `Makefile`, `PROD-READINESS.md`, `PROD-IMPLEMENTATION-PLAN.md`

## Next concrete action

1. Commit P0-A as `feat(worker): arq pipeline jobs + cron scheduler`
2. Resolve D2 (token storage) then start P0-B admin wiring

## Blocked on

- P0-B: token storage decision (cookie vs localStorage) — recommended httpOnly cookie

---

*Last updated: 2026-05-25*
