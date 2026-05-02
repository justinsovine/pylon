# WO-010: Worker harness tests

## Scope
Tests for spawn_worker, monitor_decisions, account rotation, worktree ops. Medium.

## Files to read
- src/pylon/harness/worker.py (full file: all harness functions)
- src/pylon/harness/ipc.py (full file: IPC helpers used by monitor)
- tests/conftest.py (full file: fixtures)
- tests/factories.py (full file: factories)

## Key context

Key functions to test:
```python
async def acquire_account(pipeline_id, phase, timeout) -> WorkerSession | None
async def mark_worker_running(session_id, pid)
async def release_worker(session_id, exit_code, error)
async def spawn_worker(pipeline_id, phase, notes_path, account, worktree_path) -> Process
async def monitor_decisions(pylon_dir, pipeline_id, phase, proc, notify_fn) -> list[int]
async def kill_worker(proc, grace_period=30)
async def create_worktree(repo_path, pipeline_id, branch_name) -> Path
```

Account rotation logic (worker.py lines 20-49):
```python
active = await db.execute(
    select(WorkerSession.account).where(
        WorkerSession.status.in_(["starting", "running"])
    )
)
active_accounts = set(active.scalars().all())
available = None
for acct in settings.worker_accounts:
    if acct not in active_accounts:
        available = acct
        break
```

monitor_decisions polls for round files every 5s, reports new rounds via notify_fn.

## Changes
- [ ] tests/test_harness/test_worker.py (NEW): account rotation, monitor, kill tests

## Proposed implementation

```python
# tests/test_harness/test_worker.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from src.pylon.harness.worker import acquire_account, monitor_decisions, kill_worker
from src.pylon.models import WorkerSession


async def test_acquire_account_returns_first_available(db):
    session = await acquire_account("pipe-1", "investigate", 1200)
    assert session is not None
    assert session.account == "default"
    assert session.status == "starting"


async def test_acquire_account_skips_active(db):
    s1 = await acquire_account("pipe-1", "investigate", 1200)
    s2 = await acquire_account("pipe-2", "investigate", 1200)
    assert s2.account != s1.account


async def test_acquire_account_returns_none_when_full(db):
    for i in range(3):  # 3 = len(worker_accounts)
        await acquire_account(f"pipe-{i}", "investigate", 1200)
    result = await acquire_account("pipe-3", "investigate", 1200)
    assert result is None


async def test_monitor_detects_round_file(tmp_path):
    pylon_dir = tmp_path / ".pylon"
    pylon_dir.mkdir()
    decisions_dir = pylon_dir / "decisions"
    decisions_dir.mkdir()

    notify = AsyncMock()
    proc = MagicMock()
    proc.returncode = None  # still running

    # Write a round file during monitoring
    async def write_round_after_delay():
        await asyncio.sleep(0.1)
        (decisions_dir / "round-1.json").write_text(json.dumps({
            "decisions": [{"id": "d1", "question": "Test?", "options": []}]
        }))
        await asyncio.sleep(0.1)
        proc.returncode = 0  # process exits

    asyncio.create_task(write_round_after_delay())
    reported = await monitor_decisions(pylon_dir, "pipe-1", "refine", proc, notify)
    assert 1 in reported
    notify.assert_called_once()
```

## Decisions
- [x] RESOLVED: Use tmp_path for filesystem ops, mock git commands for worktree tests
- [x] RESOLVED: Test account rotation with real DB (matches project convention of no mocks for DB)

## Tests
Requirements: unit (async DB for account tests, tmp_path for IPC)
Run: `pytest tests/test_harness/test_worker.py`
- [ ] acquire_account returns first available account
- [ ] acquire_account skips active accounts
- [ ] acquire_account returns None when all accounts busy
- [ ] monitor_decisions detects new round files
- [ ] monitor_decisions skips rounds with existing answers
- [ ] kill_worker sends SIGTERM then SIGKILL after grace period
- [ ] release_worker updates session status and exit code

## Commit
```
test(harness): add worker harness tests

Tests for account rotation, decision monitoring, and worker lifecycle.
Real DB for account tests, tmp_path for IPC filesystem.

- Test account pool exhaustion and rotation
- Test decision file detection during monitoring
- Test graceful/forced worker termination
```

## Dependencies
blocked_by: none
blocks: wo-011

## After commit
- Update status/PROGRESS.md: check "Worker harness tests"
