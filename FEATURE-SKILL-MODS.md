# Pylon -- Skill Phase Design

## Overview

/pylon has its own phase definitions, forked from /feature's proven structure but designed from the ground up for non-interactive, structured-output execution. No terminal mode. No interactive Q&A. Every phase either runs to completion or emits structured decisions and exits.

## Phases

```
investigate → refine → plan → critique → implement → test → pr
```

Seven phases. Reduced from /feature's ten (dropped coordinate, review, announce -- those concerns are handled by the orchestrator and dashboard).

## Shared conventions (inherited from /feature)

- Notes directory per ticket: `notes/{ticket-slug}/`
- Investigation traces full data flow (not just file locations)
- Plans are staged with commit messages
- Re-entry supported (pass numbering, incremental updates)
- Specific file paths and line numbers in all analysis

## Phase definitions

### investigate

Identical in purpose to /feature's investigate. Read the codebase, trace data flows, map touchpoints, surface risks.

Output: `investigation.md` in notes directory.

Differences from /feature:
- Writes `.pylon/status.json` with progress updates
- Writes `.pylon/result.json` on completion
- No human interaction. Runs to completion or fails.

```
Status updates:
  "Reading route files" (0.1)
  "Tracing data flow through controllers" (0.3)
  "Analyzing database schema" (0.5)
  "Reviewing existing test coverage" (0.7)
  "Writing investigation.md" (0.9)
```

### refine

Purpose: make scope and approach decisions. This is where /pylon diverges most from /feature.

/feature refine: asks one question at a time, waits for human, adapts next question based on answer.

/pylon refine: analyzes all decisions needed upfront, maps dependencies, emits batched rounds.

**How it works:**

First invocation (no prior answers):
1. Read investigation.md
2. Identify every decision point (scope, approach, tradeoff, ambiguity)
3. Classify each as independent or dependent on another decision
4. Emit Round 1: all independent decisions
5. Write `.pylon/decisions/round-1.json`
6. Write `.pylon/result.json` with status `awaiting_decisions`
7. Exit

Subsequent invocations (answers exist):
1. Read round-N-answers.json
2. Apply answers to notes
3. Check: are there dependent decisions now unlocked?
4. If yes: emit next round, exit with `awaiting_decisions`
5. If no: finalize notes, exit with `complete`

**Decision format:**

```json
{
  "round": 1,
  "total_estimated_rounds": 2,
  "decisions": [
    {
      "id": "d001",
      "question": "Input validation approach for new form fields",
      "context": "3 existing forms use server-side Livewire rules. No client-side library installed.",
      "options": [
        {
          "key": "A",
          "label": "Server-side only (Livewire rules)",
          "tradeoff": "Consistent with codebase. Roundtrip for validation."
        },
        {
          "key": "B",
          "label": "Client + server validation",
          "tradeoff": "Better UX. Adds dependency. Duplicates logic."
        }
      ],
      "recommendation": "A",
      "recommendation_why": "Matches existing patterns. Livewire wire:dirty handles feedback.",
      "depends_on": null,
      "unlocks": ["d004"]
    }
  ]
}
```

**Decision rules:**
- 2-4 concrete options per decision (never "it depends")
- Every option has a one-sentence tradeoff
- Always provide a recommendation with reasoning
- Independent decisions go in the same round
- Dependent decisions go in later rounds
- If a decision cannot be made with available information, say what's missing

### plan

Produces staged implementation plan from investigation + refine decisions.

Runs to completion (no decisions). Output: `implementation-plan.md`

Plan structure (same as /feature):
- Stages with clear boundaries
- Commit message per stage
- Files to modify listed per stage
- Testing checklist
- Deployment notes

Progress reporting via status.json.

If planning reveals a decision that refine missed (rare), emit it as a decision round rather than guessing. This is a round-trip: emit decision, exit, get answer, re-invoke to complete the plan.

### critique

Reviews the implementation plan. Vets claims against codebase.

Similar to refine's batch emission model:

1. Read implementation-plan.md
2. Verify every claim (file exists? function signature matches? relationship correct?)
3. Identify risky assumptions, missing steps, incorrect references
4. Emit as decision rounds:
   - Yes/no confirmations: "Plan assumes single webhook secret per tenant. Correct?"
   - Fix proposals: "Stage 3 references UserController@export but method is on WorkerProfileController@exportData. Fix? [Yes, update plan / No, the plan is correct]"
   - Missing steps: "No migration for the new column in stage 2. Add migration stage before this? [Yes / No, handled elsewhere]"

Critique decisions tend to be binary (confirm/deny) vs refine's multi-option choices.

After all critique answers received, the plan is updated with fixes applied.

### implement

Executes the plan stage by stage. Commits after each stage.

Runs to completion (normally no decisions).

Progress: stage N of M reported to status.json.

**Scope-change escape hatch:** if implementation reveals something the plan didn't anticipate and the adjustment is more than trivial:
- Emit a decision: "Plan didn't account for X. Options: A) adapt inline, B) stop and re-plan"
- This is rare but prevents the agent from silently absorbing scope creep

On completion, result.json includes:
- Files modified/created
- Commits made (hashes and messages)
- Any deviations from plan

### test

Write and run tests for the implemented feature.

Runs to completion. Output: test files + result.json with pass/fail counts.

If tests reveal a bug in implementation:
- Simple fix: fix it, note in result
- Ambiguous fix: emit decision ("Test X fails. Two possible fixes: A or B")

### pr

Clean up diff, open PR on GitHub.

Runs to completion. Output: PR URL in result.json.

PR description includes:
- Link to Asana ticket
- Summary of changes
- Decision log link (dashboard URL)
- Files changed
- Test results

## File protocol

### .pylon/ directory structure

```
notes/ticket-slug/
  investigation.md
  implementation-plan.md
  .pylon/
    status.json                     # progress (updated during execution)
    result.json                     # final outcome (written on exit)
    decisions/
      round-1.json                  # emitted by agent
      round-1-answers.json          # written by harness after human answers
      round-2.json
      round-2-answers.json
```

### status.json

```json
{
  "phase": "implement",
  "state": "running",
  "progress": 0.6,
  "message": "Stage 3 of 5: Writing Livewire component",
  "updated_at": "2026-05-01T10:30:00Z"
}
```

States: analyzing, emitting_decisions, awaiting_decisions, applying_answers, running, completing, complete, failed

### result.json

Success:
```json
{
  "phase": "investigate",
  "status": "complete",
  "summary": "Scanned 34 files. 3 existing export patterns found. 2 security risks flagged.",
  "artifacts_updated": [],
  "artifacts_created": ["investigation.md"],
  "completed_at": "2026-05-01T02:34:00Z"
}
```

Awaiting decisions:
```json
{
  "phase": "refine",
  "status": "awaiting_decisions",
  "round": 1,
  "decisions_count": 3,
  "completed_at": "2026-05-01T02:38:00Z"
}
```

Failure:
```json
{
  "phase": "implement",
  "status": "failed",
  "error": "Stage 3 failed: migration references column that doesn't exist",
  "retry_safe": false,
  "completed_at": "2026-05-01T11:15:00Z"
}
```

## Skill file structure

```
~/.claude/skills/pylon/
  SKILL.md              # main skill definition, argument parsing, phase routing
  phases/
    investigate.md
    refine.md
    plan.md
    critique.md
    implement.md
    test.md
    pr.md
```

Each phase file contains full instructions for that phase in Pylon mode. No terminal fallback. No conditional branching. Clean, single-purpose instructions.

## Building the skill

Start with investigate and refine. These are the two phases needed for Pylon v1 ("overnight investigate, morning refine"). Plan through PR can be added incrementally.

Test each phase standalone:
```bash
claude -p "/pylon investigate --notes=test-ticket --context=Add export feature to worker profiles"
```

Verify:
- .pylon/status.json written with progress
- .pylon/result.json written on exit
- For refine: .pylon/decisions/round-1.json written with valid schema
- No interactive prompts issued
