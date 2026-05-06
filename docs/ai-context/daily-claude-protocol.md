# Daily Claude Code Protocol — DarijaAI

> The operating spec for every session. Read once at session start, then put it down.
> This file is ~600 tokens. Load it only when onboarding or checking rules.
> For daily use: the session-start-prompt.md already triggers the right behavior.

---

## 1. Session Start Checklist

Execute in this exact order. Do not skip steps.

```
[ ] 1. Run /context — note the token count before anything is loaded
[ ] 2. Read task-memory/current-focus.md — what is the active task?
[ ] 3. Read task-memory/active-constraints.md — what is forbidden or blocked?
[ ] 4. Identify task type → consult task-routing.md if uncertain
[ ] 5. Load exactly ONE domain file from docs/ai-context/ for this task
[ ] 6. Report estimated token budget (CLAUDE.md ~2.9K + files loaded so far)
[ ] 7. State the task and plan out loud — wait for confirmation before coding
```

**Hard rule**: No file reads beyond step 5 until the plan is confirmed. No code until step 7.

---

## 2. Task Execution Protocol

### Scope
- **One task per session.** If a second task surfaces, note it in `current-focus.md` and defer.
- No broad repository scans (`find`, `glob **/*`, reading entire directories) unless the user explicitly types "scan the repo" or equivalent.
- Load source files only as needed: **maximum 5 source files before stating a plan**.

### Before coding
1. State which files will be modified.
2. State what change will be made and why.
3. Wait for user confirmation (or proceed if the user has pre-approved with "go ahead").

### While coding
- Touch only the files required by the stated plan. If an unrelated file needs a fix, stop and ask.
- After each meaningful change (a complete function, a complete component, a migration): run the relevant test or lint command and report the result.
- If a test fails twice with the same approach, stop. State the failure clearly. Propose a different approach. Do not retry the same fix a third time.

### File read discipline
- Read the narrowest scope that answers the question. Prefer reading a specific function range over a full file.
- If you have already read a file this session, do not re-read it unless it has been edited.
- Never read: `uv.lock`, `pnpm-lock.yaml`, `tsconfig.tsbuildinfo`, `*.pyc`, anything in `backend/logs/`, anything in `SCREEN/`, `claude.full.backup.md`.

---

## 3. Memory Update Protocol

### When to update each file

| File | Update when | What to change |
|---|---|---|
| `task-memory/current-focus.md` | Session start + session end | Active task, modified files, next action |
| `task-memory/implementation-status.md` | A sub-task changes state | Flip ✅ / 🟡 / 🔲 / 🚫. One row only. |
| `task-memory/recent-decisions.md` | A decision is made | Add dated entry. 2 lines max per decision. |
| `task-memory/known-bugs.md` | Debugging a bug | Add on discovery. Delete immediately on fix. |
| `task-memory/pending-refactors.md` | New tech debt identified | Only if it blocks future work. Not cosmetic. |
| `task-memory/active-constraints.md` | A constraint appears or is lifted | Update the relevant row. |

### Rules
- Every memory file update is a single targeted edit — no rewrites.
- Remove stale entries immediately. A memory file that grows without pruning becomes noise.
- Decisions in `recent-decisions.md` older than 30 days with no open follow-up → move to `docs/DECISIONS.md` and delete.
- Never let any memory file exceed its current line count by more than 20%. If it's growing, entries are not being pruned.

---

## 4. Reset Protocol

### When to run `/clear` and start a new session

| Trigger | Action |
|---|---|
| `/context` shows messages >25% of window | Run handoff checklist, then `/clear` |
| Claude references a file or function that no longer exists | Immediate reset — context is stale |
| Claude repeats the same wrong fix twice | Reset — do not retry in the same session |
| Claude edits a file it has not read this session | Stop, undo the change, reset |
| A major sub-task is fully committed and merged | Clean break — start fresh for next task |
| Session has been running >3 hours | Reset regardless of apparent health |

### Handoff checklist (run before every `/clear`)

```
[ ] 1. Commit or stash all in-progress work
[ ] 2. Update task-memory/current-focus.md with exact next action
[ ] 3. Update task-memory/implementation-status.md for any state changes
[ ] 4. Log any decisions in task-memory/recent-decisions.md
[ ] 5. Note any new bugs in task-memory/known-bugs.md
[ ] 6. Copy the "Next session starting prompt" from the end-of-session output
```

---

## 5. Forbidden Behaviors

These are never acceptable. If Claude does any of these, stop and reset.

| Behavior | Why it's forbidden |
|---|---|
| Reading the entire repository or large directory trees | Context explosion — 50K+ tokens wasted |
| Reading `uv.lock` or `pnpm-lock.yaml` | 167KB and 227KB — zero AI decision value |
| Reading `backend/logs/` without an explicit debugging request | Up to 600KB of runtime noise |
| Loading `claude.full.backup.md` for any reason | 17K token duplicate of `CLAUDE.md` |
| Reading prompt `.md` files as documentation | `localizer_v1.md` is a product prompt (52KB), not project context |
| Continuing a broken approach after 2 failed attempts | Sunk cost — change strategy or ask |
| Making code changes before stating a plan | Violates the planning gate in §2 |
| Touching files outside the stated task scope | Scope creep — creates untested side effects |
| Using `pip` or `npm` instead of `uv` and `pnpm` | Wrong toolchain — will break the project |
| Using GPT/OpenAI for Arabic content decisions | Claude only for Arabic — validated (ADR-002) |

---

## 6. End-of-Session Checklist

Run this before closing any session. Output it explicitly as a structured summary.

```
[ ] 1. FILES CHANGED
       List every file modified this session with one-line description of the change.

[ ] 2. DECISIONS MADE
       List any decisions that affect future code (tech choice, architecture, product rule).
       If none: "No new decisions."

[ ] 3. MEMORY UPDATED
       Confirm which task-memory/ files were updated this session.
       If none needed: "No memory updates required."

[ ] 4. TEST COMMANDS
       Exact commands to verify the work:
       e.g., "cd backend && uv run pytest tests/integration/ -v"
       e.g., "cd frontend && pnpm tsc --noEmit"

[ ] 5. NEXT SESSION STARTING PROMPT
       A self-contained 3–5 sentence prompt the user can paste to resume exactly here.
       Must include: what was just completed, what file to start with, what the next action is.
```

---

## Token budget reference

| Context state | Approx tokens | Health |
|---|---|---|
| CLAUDE.md + 2 memory files + 1 domain file | ~5,000 | Excellent |
| + 3 source files | ~9,000 | Good |
| + 5 source files | ~13,000 | Acceptable |
| + broad exploration or large files | >30,000 | Danger — approaching reset |
| Messages >25% of `/context` window | varies | Reset threshold |
