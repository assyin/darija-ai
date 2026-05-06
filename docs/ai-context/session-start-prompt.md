# Session Start Prompt

> Paste the block between the `---` lines as your first message in every new Claude Code session.
> Customize the [TASK] section or leave it blank to resume from current-focus.md.
> Do not modify anything else in the prompt.

---

```
DarijaAI session start.

Read these two files only — nothing else yet:
1. docs/ai-context/task-memory/current-focus.md
2. docs/ai-context/task-memory/active-constraints.md

Then report:
- Active task (from current-focus.md)
- Any constraints that apply to this session
- Current token budget (run /context)
- Which single domain file you recommend loading from docs/ai-context/

Do not read any other files. Do not write any code. Do not scan the repo.
Wait for my confirmation before proceeding.

[TASK: leave blank to continue current-focus.md, or describe a specific task here]
```

---

## Variants

### Resume interrupted work
Replace `[TASK]` with:
```
[TASK: Resuming from last session. Check current-focus.md for exact next action.]
```

### Start a specific new task
Replace `[TASK]` with:
```
[TASK: <describe what you want to build or fix in one sentence>]
```

### Debug a specific issue
Replace `[TASK]` with:
```
[TASK: Debugging — <describe the symptom>. Also read task-memory/known-bugs.md.]
```

### Planning / architecture session
Replace `[TASK]` with:
```
[TASK: Planning session. After memory files, load docs/ai-context/roadmap.md and task-memory/implementation-status.md. No code this session.]
```

---

## What Claude should do after you paste this

1. Read the two memory files (nothing else).
2. Output a short status block:

```
TASK:        [what's being worked on]
CONSTRAINTS: [anything blocked or forbidden this session]
TOKENS USED: [number from /context]
RECOMMEND:   [one domain file to load]
READY TO:    [next concrete action]
```

3. Stop and wait for your go-ahead.

If Claude does anything other than steps 1–3 (reads extra files, writes code, scans the repo), that is a protocol violation — paste the prompt again or run `/clear`.

---

## Why this prompt works

- Loads only ~750 tokens of memory before you've approved anything.
- Forces Claude to surface the current state explicitly before touching code.
- The confirmation gate prevents wasted work on the wrong task.
- The token report tells you immediately if the session is starting healthy.
