# WO-012: Skill phase manual test protocol

## Scope
Checklist and fixture scripts for manually testing each /pylon phase with `claude -p` against onboard repo. Small.

## Files to read
- status/backlog/critical-path.md (lines 36-49: skill phase items)
- src/pylon/harness/ipc.py (full file: IPC file format reference)
- src/pylon/tasks/pipeline.py (lines 54-97: _run_phase setup sequence)

## Key context

Worker is invoked as:
```python
proc = await asyncio.create_subprocess_exec(
    "claude", "-p", f"/pylon {phase} --notes={notes_path}",
    "--output-format", "text",
    env=env, cwd=cwd,
)
```

Required env vars:
```
PYLON_WORKER=true
PYLON_PIPELINE_ID=<uuid>
PYLON_PHASE=<phase>
PYLON_NOTES_PATH=<path>
PYLON_API_URL=http://localhost:8000
PYLON_API_KEY=change-me
```

Notes dir must contain:
- `.pylon/config.json` (pipeline_id, phase)
- `ticket.json` (title, description, assignee, repo)

For investigate: pre-investigation output files in notes dir.
For refine with answers: `.pylon/decisions/round-N-answers.json`

## Changes
- [ ] tests/manual/setup-test-phase.sh (NEW): Script to create notes dir, write config, set env
- [ ] tests/manual/TEST-PHASES.md (NEW): Step-by-step checklist per phase
- [ ] tests/manual/sample-ticket.json (NEW): Onboard repo test ticket context

## Proposed implementation

```bash
#!/bin/bash
# tests/manual/setup-test-phase.sh
# Usage: ./setup-test-phase.sh <phase> <repo_path>

PHASE=${1:-investigate}
REPO=${2:-../onboard}
PIPELINE_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
NOTES_PATH="/tmp/pylon-test-$PIPELINE_ID"

mkdir -p "$NOTES_PATH/.pylon/decisions"

cat > "$NOTES_PATH/.pylon/config.json" << EOF
{"pipeline_id": "$PIPELINE_ID", "phase": "$PHASE"}
EOF

cp "$(dirname $0)/sample-ticket.json" "$NOTES_PATH/ticket.json"

echo "Notes path: $NOTES_PATH"
echo "Run:"
echo "  cd $REPO"
echo "  PYLON_WORKER=true PYLON_PIPELINE_ID=$PIPELINE_ID PYLON_PHASE=$PHASE PYLON_NOTES_PATH=$NOTES_PATH claude -p '/pylon $PHASE --notes=$NOTES_PATH' --output-format text"
```

TEST-PHASES.md: per-phase checklist of what to verify in output files.

## Decisions
- [x] RESOLVED: Test against onboard repo first (most mature, 33 tests)
- [ ] ASK: Which Asana ticket to use as test fixture? Need a real ticket with enough context for investigate/refine.

## Tests
Requirements: manual (real claude -p, real repo)
- [ ] investigate: produces result.json with status "complete", summary in notes
- [ ] refine: produces decisions/round-1.json with structured options
- [ ] plan: produces implementation plan in result.json
- [ ] critique: produces review decisions or approves plan
- [ ] implement: makes code changes and commits
- [ ] test: writes and runs tests
- [ ] pr: opens pull request

## Commit
```
test(manual): add skill phase test protocol and setup script

Setup script creates notes directory structure for manual testing
each /pylon phase with claude -p against onboard repo.

- Add setup-test-phase.sh for quick test environment creation
- Add TEST-PHASES.md with per-phase verification checklist
- Add sample-ticket.json fixture
```

## Dependencies
blocked_by: none
blocks: none

## After commit
- Check off "Test each phase manually with `claude -p`" in status/backlog/critical-path.md (when phases actually pass)
