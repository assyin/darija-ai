# Session Reset Strategy — DarijaAI

> Defines when to clear context, how to hand off, and how to start clean.

---

## Maximum recommended context size

| Threshold | Action |
|---|---|
| Messages >20% of context (`/context` output) | Consider compressing — write a handoff and start fresh |
| Active session >3 hours of continuous work | Strong signal to reset |
| Working across 3+ different domains in one session | Split into separate sessions |
| `/context` shows >100K tokens used | Reset immediately |

**Target**: Keep total active tokens under 50K for a focused task session. Under 20K for a precise, surgical task.

---

## Signs of context rot (reset immediately)

- Claude references code or file paths that no longer exist.
- Claude contradicts a decision made earlier in the same session.
- Claude repeats questions or asks for information already provided.
- Suggestions become generic ("you could use a service layer here") instead of project-specific.
- Code suggestions use the wrong stack (e.g., `requests` instead of `httpx`, `npm` instead of `pnpm`).
- Claude stops following established patterns (e.g., forgetting RTL conventions, forgetting async rules).
- Response quality on Darija/Arabic-specific questions degrades.

---

## When to clear context

**Clear context (start a new session) when:**
1. A discrete feature is complete and committed — clean break.
2. Switching to a completely different domain (e.g., from backend services to deployment infra).
3. Any of the "context rot" signs above appear.
4. You've been working continuously for >3 hours.
5. About to start a long exploratory task (reading many files) — start fresh to avoid cross-contamination.

**Do NOT clear context when:**
1. Mid-implementation of a feature that spans multiple files — finish it first.
2. You're in the middle of debugging — context is the debugging state.
3. You just loaded domain files — no point resetting immediately.

---

## Handoff protocol (before resetting)

Do this before ending a session that has work in progress:

1. **Commit or stash** all in-progress changes.
2. **Update `docs/ai-context/active-tasks.md`**:
   - What's complete
   - What's in progress (with exact file names)
   - What's next
   - Any new decisions made
3. **Log decisions** in `docs/DECISIONS.md` if any architecture or product choices were made.
4. **Note the next command** — the exact thing to do when resuming (e.g., "run `make test` then push the branch").

---

## Starting a new session cleanly

```
1. CLAUDE.md auto-loads (~2,900 tokens) ✓
2. Read docs/ai-context/active-tasks.md → what was I doing?
3. Route to 1-2 domain files per task-routing.md → load only those
4. Read the 2-4 specific files you'll touch → no broad exploration
5. Work with focused context from the start
```

**Do not:**
- Load all domain files at once
- Start with broad `find` / glob sweeps across the whole repo
- Re-read files you've already read unless they've changed

---

## When to create a formal handoff document

Create a standalone handoff note (in `docs/ai-context/active-tasks.md` or a temp file) when:

- A feature is mid-implementation and will take >1 more session to complete.
- You're blocked on an external dependency (API key, stakeholder decision, etc.).
- You're handing the session off to a different context (e.g., switching machines).
- The task involves a complex sequence of steps that must not be forgotten.

**Handoff document should contain:**
- Current state (what's done, what's not)
- Exact files modified
- Decisions made and rationale
- Next concrete step (command or file to open)
- Any blockers and their status

---

## Context efficiency targets

| Session type | Target token budget |
|---|---|
| Surgical fix (single file) | <10K tokens |
| Feature implementation (2-4 files) | 15–30K tokens |
| Full stack feature | 30–50K tokens |
| Architecture / planning session | 20–40K tokens |
| Debug session | 20–40K tokens (front-loaded with logs/context) |
