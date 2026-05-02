# WO-009: Celery task tests

## Scope
Tests for run_phase, poll_asana, overnight_batch with mocked subprocess and external calls. Medium.

## Files to read
- src/pylon/tasks/pipeline.py (full file: run_phase, overnight_batch, _run_phase)
- src/pylon/tasks/asana.py (lines 60-85: poll_asana)
- src/pylon/tasks/celery_app.py (full file, small: app config)
- tests/conftest.py (full file: fixtures)
- tests/factories.py (full file: factories)

## Key context

run_phase entry point (pipeline.py lines 42-51):
```python
@app.task(bind=True, max_retries=2, soft_time_limit=2700, time_limit=3000, acks_late=True)
def run_phase(self, pipeline_id: str, phase: str, round_answers: dict | None = None):
    timeout = settings.phase_timeouts.get(phase, 1800)
    try:
        result = asyncio.run(_run_phase(pipeline_id, phase, timeout, round_answers))
    except SoftTimeLimitExceeded:
        asyncio.run(_handle_timeout(pipeline_id, phase))
        return {"status": "timed_out", "phase": phase}
    return result
```

_run_phase calls (in order): write_config, _notify_internal("phase-started"), _get_pipeline_info, write_ticket_context, create_worktree, run_pre_investigation (investigate only), write_answers_file, acquire_account, spawn_worker, mark_worker_running, run_worker_with_monitor, release_worker, read_result, _notify_internal(completed/failed).

Key: tests should mock at the subprocess boundary (spawn_worker) and httpx calls (_notify_internal). DB operations use real test DB.

## Changes
- [ ] tests/test_tasks/test_pipeline.py (NEW): run_phase and overnight_batch tests
- [ ] tests/test_tasks/test_asana.py (NEW): poll_asana tests

## Proposed implementation

```python
# tests/test_tasks/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.factories import make_ticket, make_pipeline


@patch("src.pylon.tasks.pipeline._notify_internal", new_callable=AsyncMock)
@patch("src.pylon.tasks.pipeline.spawn_worker")
@patch("src.pylon.tasks.pipeline.acquire_account")
async def test_run_phase_investigate_success(
    mock_acquire, mock_spawn, mock_notify, db, tmp_path
):
    # Setup: ticket + pipeline in DB, mock worker that writes result.json
    # Assert: notify called with phase-started and phase-completed
    pass


@patch("src.pylon.tasks.pipeline._notify_internal", new_callable=AsyncMock)
async def test_run_phase_worker_failure_notifies_failed(mock_notify, db, tmp_path):
    # Setup: worker returns non-zero exit code
    # Assert: notify called with phase-failed
    pass
```

## Decisions
- [x] RESOLVED: Mock spawn_worker to return fake process, not actual subprocess
- [x] RESOLVED: Use tmp_path for notes/pylon dirs, no real filesystem state

## Tests
Requirements: unit (async DB, mocked externals)
Run: `pytest tests/test_tasks/`
- [ ] run_phase calls phase-started notification
- [ ] run_phase on investigate triggers pre-investigation
- [ ] run_phase with successful worker calls phase-completed
- [ ] run_phase with failed worker calls phase-failed
- [ ] run_phase with rate limit error retries
- [ ] overnight_batch dispatches correct number of pipelines
- [ ] poll_asana creates ticket and pipeline from Asana task

## Commit
```
test(tasks): add Celery task tests for run_phase and poll_asana

Tests verify phase lifecycle: start notification, worker dispatch,
completion/failure handling. Mock subprocess and external HTTP.

- Test run_phase happy path and failure modes
- Test overnight_batch pipeline dispatch
- Test poll_asana ticket creation
```

## Dependencies
blocked_by: none
blocks: wo-011

## After commit
- Update status/PROGRESS.md: check "Celery task tests (mocked subprocess)"
