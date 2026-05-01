# Pylon -- Decision Protocol

## Overview

The decision protocol defines how Claude Code workers emit structured questions and how the system delivers human answers back. This is the core contract that makes async Q&A work.

## Decision lifecycle

```
Worker emits decision round
  → Harness writes to .pylon/decisions/round-N.json
  → Harness POSTs to API: POST /api/decisions/rounds
  → API stores in Postgres, sets pipeline status = awaiting_decisions
  → Dashboard shows decision cards to assigned dev
  → Dev answers (clicks option or writes freeform)
  → API stores answer, checks if round complete
  → When all decisions in round answered:
    → API writes .pylon/decisions/round-N-answers.json
    → API triggers next worker invocation with answers
    → Worker reads answers, continues phase
    → Worker may emit round N+1 (dependent decisions)
    → Or phase completes
```

## Round-based batching

### Why rounds instead of one-at-a-time

Interactive /feature refine asks one question, waits, asks the next. This works in terminal but creates terrible dashboard UX (dev gets pinged 7 times for 7 questions).

Rounds batch independent decisions together. Dev sees all of round 1 at once, answers them all, then round 2 appears with decisions that depended on round 1 answers.

### How dependency works

```
Round 1 (independent):
  d001: "Validation approach?" (server-only / client+server / progressive)
  d002: "Empty state design?" (illustration / text-only / skeleton)
  d003: "Include audit logging?" (yes / no / defer)

Round 2 (depends on round 1):
  d004: "Which client validation library?" (depends on d001=B or d001=C)
         Only emitted if d001 answer was B or C.
  d005: "Audit log retention period?" (depends on d003=yes)
         Only emitted if d003 answer was yes.
```

If d001=A and d003=no, round 2 has zero decisions and phase completes immediately.

### Round emission from /feature phases

The refine phase needs modification to support batch emission. Current behavior:

```
# Current (interactive terminal)
1. Ask question 1
2. Wait for answer
3. Ask question 2 (may depend on answer 1)
4. Wait for answer
...
```

Pylon behavior:

```
# Pylon mode (PYLON_WORKER=true)
1. Analyze investigation notes
2. Identify ALL decisions needed
3. Map dependencies between decisions
4. Emit round 1: all decisions with no dependencies
5. Write round-1.json to .pylon/decisions/
6. Exit with status "awaiting_decisions"

# After round 1 answers arrive, new invocation:
7. Read round-1-answers.json
8. Apply answers to notes
9. Evaluate: are there dependent decisions now unlocked?
10. If yes: emit round 2, exit with "awaiting_decisions"
11. If no: phase complete, exit with "complete"
```

Each round is a separate Claude Code invocation. No long-lived process.

## File-based IPC

Workers communicate through the filesystem. The .pylon/ directory inside the notes folder is the mailbox.

### Directory structure

```
notes/ticket-slug/
  investigation.md
  implementation-plan.md
  .pylon/
    config.json                     # pipeline metadata
    status.json                     # current state, updated by worker
    decisions/
      round-1.json                  # worker emits
      round-1-answers.json          # harness writes after human answers
      round-2.json                  # worker emits (next invocation)
      round-2-answers.json          # harness writes
    result.json                     # final phase result
```

### config.json (written by harness before spawning worker)

```json
{
  "pipeline_id": "uuid",
  "ticket_slug": "offer-letter-redesign",
  "asana_gid": "1234567890",
  "repo": "onboard",
  "phase": "refine",
  "pass_number": 1,
  "assignee": "justin",
  "worktree_path": "/app/worktrees/offer-letter-redesign",
  "prior_answers": {}
}
```

### status.json (updated by worker during execution)

```json
{
  "phase": "refine",
  "state": "analyzing",
  "progress": 0.3,
  "message": "Mapping decision dependencies from investigation notes",
  "updated_at": "2026-05-01T02:15:00Z"
}
```

States: analyzing, emitting_decisions, awaiting_decisions, applying_answers, completing, complete, failed

### round-N.json (emitted by worker)

```json
{
  "round": 1,
  "phase": "refine",
  "total_expected_rounds": 2,
  "decisions": [
    {
      "id": "d001",
      "question": "Input validation approach for the new form fields",
      "context": "Investigation found 3 existing forms in onboard use server-side validation via Livewire component rules. No client-side validation library is currently installed. Adding client-side would require a new dependency.",
      "options": [
        {
          "key": "A",
          "label": "Server-side only (Livewire rules)",
          "tradeoff": "Consistent with existing patterns. Slightly worse UX (roundtrip for validation). Zero new dependencies."
        },
        {
          "key": "B",
          "label": "Client-side + server-side",
          "tradeoff": "Better UX (instant feedback). Adds a JS validation library. Validation logic duplicated in two places."
        },
        {
          "key": "C",
          "label": "Progressive enhancement via Alpine.js",
          "tradeoff": "Good UX without new dependency (Alpine already loaded). More complex component code. Validation still authoritative server-side."
        }
      ],
      "recommendation": "A",
      "recommendation_why": "Matches codebase patterns. Livewire's wire:dirty and wire:loading provide adequate UX feedback without client validation. Three existing forms work this way with no complaints.",
      "depends_on": null,
      "unlocks": ["d004"]
    },
    {
      "id": "d002",
      "question": "Empty state design for the new dashboard widget",
      "context": "...",
      "options": [...],
      "recommendation": "B",
      "recommendation_why": "...",
      "depends_on": null,
      "unlocks": []
    }
  ]
}
```

### round-N-answers.json (written by harness after human responds)

```json
{
  "round": 1,
  "answers": [
    {
      "id": "d001",
      "choice": "A",
      "note": "",
      "answered_by": "justin",
      "answered_at": "2026-05-01T09:23:00Z"
    },
    {
      "id": "d002",
      "choice": "B",
      "note": "Use the illustration from the brand kit, not a generic placeholder",
      "answered_by": "justin",
      "answered_at": "2026-05-01T09:24:00Z"
    }
  ]
}
```

### result.json (written by worker when phase completes)

```json
{
  "phase": "refine",
  "status": "complete",
  "rounds_completed": 2,
  "decisions_made": 5,
  "artifacts_updated": ["investigation.md"],
  "artifacts_created": [],
  "summary": "5 scope decisions resolved across 2 rounds. Investigation notes updated with decisions. Ready for plan phase.",
  "completed_at": "2026-05-01T09:35:00Z"
}
```

Or on failure:

```json
{
  "phase": "refine",
  "status": "failed",
  "error": "Claude Code process exited with code 1",
  "stderr_tail": "Error: Rate limit exceeded. Retry after 60 seconds.",
  "rounds_completed": 1,
  "retry_safe": true,
  "completed_at": "2026-05-01T09:35:00Z"
}
```

## Decision types

Not all decisions are multiple-choice. The protocol supports:

### Multiple choice (most common)
Options array with 2-5 choices. Human picks one.

### Yes/No confirmation
Two options. Usually "the plan assumes X, confirm?"

### Freeform input
No options array. Human writes text. Used when the agent needs information it can't infer.

```json
{
  "id": "d006",
  "question": "What is the expected SLA for webhook processing?",
  "context": "Investigation found no documented SLA. Implementation approach differs significantly between <1s and <30s targets.",
  "options": null,
  "input_type": "text",
  "placeholder": "e.g., '5 seconds' or 'best effort, no hard SLA'",
  "recommendation": null,
  "recommendation_why": null
}
```

### Accept recommendation (shortcut)

Dashboard shows a "Accept all recommendations" button for a round. If the agent's recommendations look right, dev clicks once instead of answering each individually. Answer records show source: "auto" with note: "accepted agent recommendation".

This is the fast path for experienced devs who trust the agent's judgment on routine decisions. Critical or novel decisions should still get individual attention.

## Edge cases

### Dev disagrees with all options

Freeform note field on every decision allows "None of these. Instead, do X." Worker's next invocation reads this and adapts.

### Dev wants to change a prior answer

Dashboard allows editing answered decisions if the next round hasn't been applied yet. Once applied, the answer is locked (but dev can re-run the phase, which starts a new pass).

### Worker emits zero decisions

Phase had no ambiguity. Moves straight to next phase. Logged as a zero-decision round for audit.

### Worker crashes before emitting decisions

No round-N.json file exists. Harness detects timeout or exit code, marks phase_run as failed, creates new worker session for retry. Notes directory is intact, retry starts from same phase.

### Two rounds have circular dependency

Shouldn't happen if the agent maps dependencies correctly. If it does, harness detects the cycle (round N+1 depends on unanswered decision from round N that was supposed to be in round N) and fails the phase with a clear error. Human intervenes via terminal /feature.
