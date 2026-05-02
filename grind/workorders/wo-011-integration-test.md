# WO-011: Integration test: full pipeline loop

## Scope
End-to-end test: ticket creation -> investigate -> decisions -> answer -> next phase. Fake subprocess emitting IPC files instead of real Claude. Large.

## Files to read
- src/pylon/tasks/pipeline.py (full file: _run_phase orchestration)
- src/pylon/harness/worker.py (lines 77-112: spawn_worker)
- src/pylon/harness/ipc.py (full file: file format reference)
- src/pylon/api/internal.py (full file: state machine)
- src/pylon/api/decisions.py (lines 56-122: answer submission + resume)
- tests/conftest.py (full file: fixtures)

## Key context

Fake worker script must produce these IPC files:

For investigate phase (complete immediately):
```json
// .pylon/result.json
{"status": "complete", "summary": "Investigation complete"}
```

For refine phase (emit decisions, wait for answers):
```json
// .pylon/decisions/round-1.json
{
  "decisions": [
    {"id": "d1", "question": "Export format?", "options": [
      {"key": "A", "label": "CSV", "tradeoff": "Simple"},
      {"key": "B", "label": "XLSX", "tradeoff": "Rich"}
    ], "recommendation": "A", "recommendation_why": "Simpler"}
  ]
}
```

spawn_worker call (worker.py lines 100-112):
```python
proc = await asyncio.create_subprocess_exec(
    "claude", "-p", prompt, "--output-format", "text",
    env=env, cwd=cwd,
    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
)
```

Answer submission triggers run_phase.delay (decisions.py line 117):
```python
run_phase.delay(str(phase_run.pipeline_id), phase_run.phase, round_answers)
```

## Changes
- [ ] tests/fixtures/fake_worker.py (NEW): Script that reads phase from env, writes expected IPC files
- [ ] tests/test_integration.py (NEW): Full pipeline loop test

## Proposed implementation

```python
# tests/fixtures/fake_worker.py
"""Fake claude worker for integration tests.
Reads PYLON_PHASE env var, writes appropriate IPC files, exits 0."""
import json
import os
import sys
from pathlib import Path

phase = os.environ["PYLON_PHASE"]
notes = os.environ["PYLON_NOTES_PATH"]
pylon_dir = Path(notes) / ".pylon"
pylon_dir.mkdir(parents=True, exist_ok=True)

if phase == "investigate":
    (pylon_dir / "result.json").write_text(json.dumps({"status": "complete"}))
elif phase == "refine":
    decisions_dir = pylon_dir / "decisions"
    decisions_dir.mkdir(exist_ok=True)
    answers_file = pylon_dir / "decisions" / "round-1-answers.json"
    if answers_file.exists():
        (pylon_dir / "result.json").write_text(json.dumps({"status": "complete"}))
    else:
        (decisions_dir / "round-1.json").write_text(json.dumps({
            "decisions": [{"id": "d1", "question": "Approach?", "options": [
                {"key": "A", "label": "Simple", "tradeoff": "Less work"},
            ], "recommendation": "A", "recommendation_why": "Faster"}],
        }))
        (pylon_dir / "result.json").write_text(json.dumps({
            "status": "awaiting_decisions", "round": 1,
        }))
else:
    (pylon_dir / "result.json").write_text(json.dumps({"status": "complete"}))

sys.exit(0)
```

```python
# tests/test_integration.py
import pytest
from unittest.mock import patch, AsyncMock

from tests.factories import make_ticket, make_pipeline


@patch("src.pylon.harness.worker.spawn_worker")
@patch("src.pylon.tasks.pipeline._notify_internal", new_callable=AsyncMock)
async def test_full_pipeline_investigate_to_refine(mock_notify, mock_spawn, db, tmp_path):
    """Test: investigate completes -> auto-advances to refine -> emits decisions."""
    # 1. Create ticket + pipeline
    # 2. Call _run_phase("investigate") with fake worker
    # 3. Assert phase-completed notification sent
    # 4. Assert next phase dispatched (mock run_phase.delay)
    # 5. Call _run_phase("refine") with fake worker
    # 6. Assert decisions-emitted notification sent
    # 7. Submit answers via API
    # 8. Assert phase resumes
    pass
```

## Decisions
- [x] RESOLVED: Fake subprocess via Python script, not shell script (Decision 4, Option A)
- [x] RESOLVED: Mock spawn_worker to run fake_worker.py instead of claude
- [ ] ASK: How many phases to cover in integration test? Recommend: investigate + refine (proves full decision loop). Remaining phases are same code path with different IPC files.

## Tests
Requirements: integration (async DB, tmp_path filesystem)
Run: `pytest tests/test_integration.py -v`
- [ ] Pipeline created, investigate dispatched
- [ ] Investigate phase completes, auto-advances to refine
- [ ] Refine phase emits decisions, pipeline enters awaiting_decisions
- [ ] Answer submission resumes refine phase
- [ ] Refine completes after answers, advances to plan
- [ ] Failed phase with retry_safe triggers retry
- [ ] Failed phase without retries marks pipeline failed

## Commit
```
test(integration): add full pipeline loop test with fake worker

End-to-end test covering investigate -> refine decision loop. Fake
worker script emits IPC files instead of running Claude.

- Add fake_worker.py fixture script
- Test phase transitions, decision emission, answer submission
- Verify auto-advance between phases
```

## Dependencies
blocked_by: wo-008, wo-009, wo-010
blocks: none

## After commit
- Update status/PROGRESS.md: check "Integration test: full pipeline loop with mock Claude"
