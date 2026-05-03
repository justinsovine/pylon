# WO-008: Internal API endpoint tests

## Scope
Tests for phase state machine endpoints: phase-started, decisions-emitted, phase-completed, phase-failed, progress. Medium.

## Files to read
- src/pylon/api/internal.py (full file: all 5 endpoints)
- tests/conftest.py (full file: fixtures)
- tests/factories.py (full file: factory helpers)
- tests/test_api/test_pipelines.py (first 30 lines: test pattern reference)
- src/pylon/config.py (line 16: pylon_internal_key default)

## Key context

Test pattern (conftest.py):
```python
@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

Internal key header required:
```python
def verify_internal_key(x_pylon_key: str = Header()):
    if x_pylon_key != settings.pylon_internal_key:
        raise HTTPException(status_code=401, detail="invalid internal key")
```

Default key: `"change-me"`

Factory helpers available: `make_ticket`, `make_pipeline`, `make_phase_run`, `make_decision_round`, `make_decision`

Key behaviors to test:
- phase-started creates PhaseRun, updates Pipeline.status and current_phase
- decisions-emitted creates DecisionRound + Decision rows, sets pipeline status to "awaiting_decisions"
- phase-completed marks PhaseRun completed, auto-dispatches next phase via run_phase.delay
- phase-failed retries if retry_safe and under max_retries, else marks pipeline failed
- All endpoints reject missing/wrong X-Pylon-Key

## Changes
- [ ] tests/test_api/test_internal.py (NEW): 10-12 test functions

## Proposed implementation

```python
# tests/test_api/test_internal.py
import pytest
from unittest.mock import patch

from tests.factories import make_ticket, make_pipeline, make_phase_run

HEADERS = {"x-pylon-key": "change-me"}


async def test_phase_started_creates_run(client, db):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="queued")
    db.add_all([ticket, pipeline])
    await db.commit()

    resp = await client.post("/api/internal/phase-started", json={
        "pipeline_id": str(pipeline.id), "phase": "investigate",
    }, headers=HEADERS)
    assert resp.status_code == 200
    assert "phase_run_id" in resp.json()


async def test_internal_rejects_bad_key(client):
    resp = await client.post("/api/internal/phase-started", json={
        "pipeline_id": "00000000-0000-0000-0000-000000000000", "phase": "investigate",
    }, headers={"x-pylon-key": "wrong"})
    assert resp.status_code == 401


@patch("src.pylon.api.internal.run_phase")
async def test_phase_completed_dispatches_next(mock_run_phase, client, db):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="investigate", current_phase="investigate")
    phase_run = make_phase_run(pipeline, phase="investigate", status="running")
    db.add_all([ticket, pipeline, phase_run])
    await db.commit()

    resp = await client.post("/api/internal/phase-completed", json={
        "pipeline_id": str(pipeline.id), "phase": "investigate", "result": {},
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_phase"] == "refine"
    mock_run_phase.delay.assert_called_once()


async def test_phase_failed_marks_pipeline_failed(client, db):
    # ... setup pipeline with max retries exhausted
    pass
```

## Decisions
- [x] RESOLVED: Mock run_phase.delay to avoid Celery dependency in tests
- [x] RESOLVED: Mock Asana sync to avoid external calls

## Tests
Requirements: unit (async DB, no external services)
Run: `pytest tests/test_api/test_internal.py`
- [ ] phase-started creates PhaseRun, updates pipeline status
- [ ] phase-started sets started_at on first call
- [ ] decisions-emitted creates round + decisions, sets awaiting_decisions
- [ ] phase-completed advances to next phase and dispatches
- [ ] phase-completed on final phase marks pipeline completed
- [ ] phase-completed stores pr_url from result
- [ ] phase-failed retries when retry_safe and under limit
- [ ] phase-failed marks pipeline failed when retries exhausted
- [ ] all endpoints reject wrong X-Pylon-Key
- [ ] progress endpoint returns ok (stub or Redis)

## Commit
```
test(api): add internal API endpoint tests

Tests for phase state machine: started, decisions-emitted, completed,
failed. Verifies auto-advance, retry logic, and auth.

- 10+ tests covering all internal endpoints
- Mock run_phase.delay and Asana sync
- Test auth rejection on bad API key
```

## Dependencies
blocked_by: none
blocks: wo-011

## After commit
- Update status/PROGRESS.md: check "Internal API tests"
