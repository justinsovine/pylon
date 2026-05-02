# Critical Path

Items that must be done for the first end-to-end pipeline loop:
Asana ticket in -> investigation -> refine decisions -> plan -> critique decisions -> implement -> test -> PR out.

## Wiring: API -> Celery -> Worker

- [x] Pipeline create endpoint dispatches `run_phase("investigate")` via Celery
- [x] `run_phase` calls internal API on completion/failure/decisions-emitted
- [x] Phase-completed endpoint auto-dispatches next phase
- [x] Answer submission writes answer files and dispatches next worker
- [x] Phase-failed triggers retry (up to configured max)

This is the spine. Everything else hangs off it.

## Wiring: Asana -> Tickets -> Pipelines

- [x] `poll_asana` task creates Ticket rows from Asana tasks in target section
- [x] `overnight_batch` reads unstarted tickets, creates pipelines, dispatches investigate
- [x] Asana custom fields updated on phase transitions (pylon_status, pylon_pr)

## Worker harness gaps

- [x] Git worktree creation (`git worktree add`) for isolated branches
- [x] Branch creation (`git checkout -b pylon/{slug}/{phase}`)
- [x] Account rotation checking DB for active sessions (not naive round-robin)
- [x] Decision file detection triggering internal API call
- [x] Worker monitoring loop (health checks every 30s, kill stuck workers)

## Database bootstrap

- [x] Generate initial Alembic migration from models
- [x] Run migration in Docker entrypoint
- [x] Seed data script for development (sample ticket, pipeline, decisions)

## /pylon skill phases

- [x] Write skill phase files for all 7 phases (~/.claude/skills/pylon/)
- [x] Verify `--output-format text` does not suppress tool calls (blocks everything below)
- [x] Fix harness wiring gaps (see OPEN-QUESTIONS.md "Wiring gaps" section):
  - [x] Write ticket context to notes folder in `_run_phase`
  - [x] Decide on `--asana`/`--decisions` flags vs file scanning (dropped flags)
  - [x] Standardize decision options format to structured `key/label/tradeoff`
  - [x] Fix branch naming (drop phase suffix from `pylon/{slug}`)
- [ ] Test each phase manually with `claude -p` against a real onboard ticket
- [ ] Validate round-trip: skill emits decisions -> harness reads them -> API stores them

Skill files exist. Wiring gaps between skill contract and harness found during authoring.
`--output-format text` confirmed safe (2026-05-02): tool calls execute normally, flag only affects stdout format.

## Notifications

- [x] Slack webhook on decisions-emitted (dev needs to answer)
- [x] Slack webhook on phase-failed (something broke)
- [x] Slack webhook on pipeline completed (PR ready)

## Dashboard: decision flow

- [ ] Decision card partial with radio buttons and submit
- [ ] Badge partial showing pending decision count
- [ ] Board partial rendering pipeline cards in kanban columns

Devs need to be able to answer decisions and see pipeline status. Everything else is polish.
