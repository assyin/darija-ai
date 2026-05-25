# Context Hygiene System — DarijaAI

> Autonomous rules for preventing Claude Code context degradation.
> Load this file: only when diagnosing a session problem, or during weekly maintenance.
> Estimated tokens: ~2,800. Do not load during normal development sessions.

---

## 1. Context Health Scoring

Score the session by summing signal points. Check after every 30 minutes of work.

### Signal table

| Signal | Points |
|---|---|
| `/context` messages token share: <10% | 0 |
| `/context` messages token share: 10–25% | +1 |
| `/context` messages token share: 25–40% | +3 |
| `/context` messages token share: >40% | +6 |
| Files loaded this session: ≤5 | 0 |
| Files loaded this session: 6–9 | +1 |
| Files loaded this session: 10–14 | +3 |
| Files loaded this session: ≥15 | +5 |
| Same fix attempted twice with same failure | +4 |
| Plan was skipped before a code change | +3 |
| Claude edited a file it had not read | +5 |
| Claude referenced a deleted/renamed symbol | +4 |
| Claude restated the same explanation twice | +2 |
| Claude used wrong toolchain (pip, npm, requests) | +3 |
| Claude forgot a decision made earlier this session | +4 |
| Claude ignored RTL or Arabic conventions | +3 |
| Broad repo scan without user approval | +4 |

### Health levels

| Score | Level | Meaning |
|---|---|---|
| 0–3 | **Healthy** | Continue. Session is clean. |
| 4–8 | **Warning** | Pause. Run self-audit. Reload 2 memory files. |
| 9–15 | **Degraded** | Stop coding. Create handoff. Reload from scratch or split task. |
| ≥16 or any +5 signal | **Critical** | Force `/clear`. No exceptions. |

Any single **+5 signal fires Critical immediately**, regardless of total score.

---

## 2. Context Rot Detection

These are observable signals, not feelings. If you see one, act.

| Signal | How to detect | Severity |
|---|---|---|
| Editing unread file | Claude writes to a file not in this session's read list | Critical |
| Forgotten decision | Claude proposes something contradicted by earlier output | Degraded |
| Wrong stack | `pip install`, `npm run`, `requests.get()`, `Optional[X]` appear in suggestions | Warning |
| Repeated debug loop | Same test fails 3+ times with structurally identical fixes | Degraded |
| Contradictory output | Claude recommends X, then recommends not-X without new info | Degraded |
| Scope creep | Claude edits a file outside the stated task plan | Warning |
| Vagueness increase | Responses grow longer but contain fewer project-specific details | Warning |
| Missing RTL convention | Frontend code uses `ml-`, `pl-`, `left-` instead of logical properties | Warning |
| Unexplained repo scan | Claude runs `glob **/*` or reads >3 files in one message without approval | Degraded |
| Stale reference | Claude refers to `process_article.py` as "the worker" (it's a script) | Warning |

**Rule**: Two Warning signals in the same message = treat as Degraded.

---

## 3. Automatic Recovery Protocol

### Healthy (score 0–3)
- Continue normally.
- No action required.

### Warning (score 4–8)
1. Stop before the next code change.
2. Re-read `task-memory/current-focus.md` and `task-memory/active-constraints.md`.
3. Restate the task and current plan in one sentence.
4. Drop any files loaded that aren't strictly needed for this task.
5. Resume only after the restatement is confirmed.

### Degraded (score 9–15)
1. Stop all code changes immediately.
2. Run the end-of-session checklist from `daily-claude-protocol.md §6`.
3. Update all task memory files with current state.
4. Evaluate: can the remaining work fit in a fresh session? If yes → `/clear`.
5. If the task is too large for one session → split it (see §6 task granularity).
6. Do not attempt to "push through" a degraded session. Recovery costs more than reset.

### Critical (score ≥16 or any +5 signal)
1. Immediately stop. Do not write another line of code.
2. Undo any changes made after the +5 signal fired (git checkout or manual revert).
3. Update `task-memory/current-focus.md` with the last known good state.
4. Run `/clear`.
5. Start the next session with the standard session-start-prompt.

---

## 4. Long-Project Maintenance

### Weekly (every 5–7 days of active development)

```
[ ] known-bugs.md       — delete any bug marked fixed and committed
[ ] implementation-status.md — flip any sub-tasks completed this week
[ ] pending-refactors.md — remove any resolved refactors
[ ] current-focus.md    — confirm it reflects the actual current task
[ ] recent-decisions.md — archive entries >30 days old to docs/DECISIONS.md
```

Run `/context` before and after. Weekly maintenance should cost <2K tokens.

### Monthly (every 30 days)

```
[ ] roadmap.md              — move completed items to a "Shipped" section, trim
[ ] All domain context files — verify they reflect current code structure
                              (file paths, route names, table names still accurate?)
[ ] docs/ai-context/*.md    — check for duplicated knowledge across files
[ ] implementation-status.md — collapse ✅ items older than 60 days into a summary line
[ ] DECISIONS.md            — confirm all ADRs from recent-decisions.md were migrated
[ ] .claudeignore           — check if any new large generated files need blocking
```

### Stale file detection

A domain context file is stale if it references:
- A file path that no longer exists.
- A model or schema name that was renamed.
- A status (e.g., "not yet built") that has since been built.
- A constraint that has since been lifted.

Detection method: after completing any feature, skim the relevant domain file for the three things above. Fix inline — it's a 1-minute edit.

### Obsolete roadmap cleanup

Move a roadmap item to "Shipped" when:
- The feature is committed to `main`.
- At least one test covers the happy path.
- The relevant domain context file has been updated.

Do not accumulate more than 15 "not started" items in `roadmap.md`. If the list grows, it means the scope is untethered — cut or defer explicitly.

---

## 5. Memory Compaction Rules

### Hard size limits per file

| File | Max lines | Enforcement |
|---|---|---|
| `current-focus.md` | 50 | One active task. Archive completed task on overwrite. |
| `active-constraints.md` | 65 | Remove lifted constraints immediately. |
| `recent-decisions.md` | 55 | 30-day rolling. Archive to `docs/DECISIONS.md`. |
| `known-bugs.md` | 45 | Active bugs only. Delete on fix, no "recently fixed" backlog. |
| `implementation-status.md` | 130 | Collapse ✅ items quarterly into a one-line summary. |
| `pending-refactors.md` | 75 | Only blockers. Cosmetic debt → delete. |
| Any domain context file | 100 | Trim examples and rationale first; keep rules and paths. |
| `daily-claude-protocol.md` | 160 | Stable spec. Only update if a rule proves unworkable. |

### Archival rules

| Entry type | Action when expired |
|---|---|
| Decision >30 days old, no open follow-up | Move to `docs/DECISIONS.md`, delete from `recent-decisions.md` |
| Completed refactor | Delete from `pending-refactors.md` |
| Fixed bug | Delete from `known-bugs.md` immediately |
| Completed sub-task (>60 days old) | Collapse 5+ ✅ rows into `[group] — X sub-tasks shipped, see git log` |
| Shipped roadmap item | Move to `## Shipped` section in `roadmap.md`, keep 1-line summary |

### Summarization threshold

Summarize (rather than keep full entries) when:
- A section in any memory file exceeds 15 rows.
- The same project concept appears in more than 2 different memory files.
- A file has more than 20% of its content describing something that is no longer in flux.

**Rule**: A memory file that cannot be read in 60 seconds is too long.

---

## 6. AI Workflow Optimization

### Ideal session parameters

| Parameter | Target | Hard limit |
|---|---|---|
| Session duration | 45–75 minutes | 3 hours |
| Files loaded simultaneously | 4–6 | 10 |
| Source files read before planning | ≤3 | 5 |
| Tasks per session | 1 | 1 |
| `/context` checks per session | 2–3 (start, midpoint, end) | — |
| Consecutive sessions without a reset | 3 | 5 |

### Ideal task granularity

A task is right-sized if it fits this template:
> "Implement [one function / one component / one migration / one route] so that [one test passes / one user action works]."

A task is too large if it requires modifying files in more than two layers simultaneously (e.g., model + service + route + frontend all in one session). Split it.

A task is too small if it requires reading more files for context than it requires editing. Batch it with a related task.

### Ideal planning depth

Before any code change, state:
1. Which file(s) will be modified (names only).
2. What change will be made (one sentence).
3. What will verify it worked (test command or observable behavior).

That is the entire plan. No design documents. No lengthy rationale. If you can't state all three in under 60 words, the task is not scoped correctly.

### Ideal reset frequency

Reset (new session) after:
- Every committed and pushed feature.
- Every >90-minute session.
- Every domain boundary crossing (backend session → frontend session).
- Anytime the score hits Degraded or Critical.

Do not think of reset as failure. A 20-minute focused session that produces one committed, tested feature is better than a 3-hour degraded session that produces a diff no one trusts.

---

## 7. Self-Audit Checklist

Run this before every code change. Takes 30 seconds.

```
[ ] Am I loading too much?
    → /context: if messages >15% of window, drop files before proceeding.

[ ] Am I repeating a previous failure?
    → If this approach already failed once this session, stop. Change strategy.

[ ] Am I solving exactly one task?
    → If I've touched files outside the plan, revert and refocus.

[ ] Do I actually need more context?
    → Can I make this change with what I've already loaded? If yes, don't load more.

[ ] Is a reset cheaper than continuing?
    → Health score ≥9? Session >90 min? More than one +5 signal? Reset wins.
```

If the answer to any question is "no, but..." — treat it as "no."

---

## 8. Golden Rules

These 10 rules govern every Claude Code session in this project, for as long as the project exists.

**1. Load minimum, expand on demand.**
Start with 2 memory files. Add context only when a specific question cannot be answered without it.

**2. State the plan before touching any file.**
No exceptions. "I'll figure it out as I go" is how context rot starts.

**3. One task. One session. One commit.**
The session boundary and the commit boundary should be the same thing.

**4. A reset is a tool, not a failure.**
A clean 20-minute session beats a corrupted 2-hour session every time. Use `/clear` freely.

**5. Memory files are pruned, not accumulated.**
Every session that adds an entry must also remove a stale one. Size limits are hard.

**6. Never retry the same failed approach twice.**
Two identical failures = wrong approach, not bad luck. Change strategy or ask.

**7. The session-start-prompt is non-negotiable.**
Every session begins with it. No shortcutting, even for "quick fixes."

**8. Forbidden files stay forbidden.**
`backend/logs/`, `uv.lock`, `localizer_v1.md`, `claude.full.backup.md` are never loaded as context. Not even once, not even "just to check."

**9. Context health is checked, not felt.**
Run the score. Don't trust the feeling that "the session is going fine." Score it at the 30-minute mark.

**10. The end-of-session checklist closes every session.**
No session ends without: files changed, decisions logged, memory updated, test commands provided, next-session prompt written. If it's not written down, it didn't happen.
