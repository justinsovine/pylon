from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.pylon.models import DecisionRound, PhaseRun, Pipeline
from tests.factories import make_pipeline, make_phase_run, make_ticket

TEST_KEY = "test-internal-key"
HEADERS = {"x-pylon-key": TEST_KEY}
INTERNAL = "/api/internal"


@pytest.fixture
def mock_externals():
    with (
        patch("src.pylon.api.internal.settings") as mock_settings,
        patch("src.pylon.api.internal.run_phase") as mock_run_phase,
        patch("src.pylon.api.internal.sync_asana_fields", new_callable=AsyncMock),
        patch("src.pylon.api.internal.notify_decisions_pending", new_callable=AsyncMock),
        patch("src.pylon.api.internal.notify_phase_failed", new_callable=AsyncMock),
        patch("src.pylon.api.internal.notify_pipeline_completed", new_callable=AsyncMock),
        patch("src.pylon.api.internal.set_progress", new_callable=AsyncMock),
    ):
        mock_settings.pylon_internal_key = TEST_KEY
        mock_settings.max_phase_retries = 2
        yield mock_run_phase


# --- Auth ---


@pytest.mark.asyncio
async def test_rejects_missing_key(client: AsyncClient, mock_externals):
    resp = await client.post(f"{INTERNAL}/phase-started", json={
        "pipeline_id": "00000000-0000-0000-0000-000000000000",
        "phase": "investigate",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rejects_wrong_key(client: AsyncClient, mock_externals):
    resp = await client.post(f"{INTERNAL}/phase-started", json={
        "pipeline_id": "00000000-0000-0000-0000-000000000000",
        "phase": "investigate",
    }, headers={"x-pylon-key": "wrong-key"})
    assert resp.status_code == 401


# --- phase-started ---


@pytest.mark.asyncio
async def test_phase_started_creates_run(client: AsyncClient, db: AsyncSession, mock_externals):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="queued")
    db.add_all([ticket, pipeline])
    await db.commit()

    resp = await client.post(f"{INTERNAL}/phase-started", json={
        "pipeline_id": str(pipeline.id),
        "phase": "investigate",
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "phase_run_id" in data

    await db.refresh(pipeline)
    assert pipeline.status == "investigate"
    assert pipeline.current_phase == "investigate"


@pytest.mark.asyncio
async def test_phase_started_sets_started_at(client: AsyncClient, db: AsyncSession, mock_externals):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="queued")
    db.add_all([ticket, pipeline])
    await db.commit()
    assert pipeline.started_at is None

    await client.post(f"{INTERNAL}/phase-started", json={
        "pipeline_id": str(pipeline.id),
        "phase": "investigate",
    }, headers=HEADERS)

    await db.refresh(pipeline)
    assert pipeline.started_at is not None


# --- decisions-emitted ---


@pytest.mark.asyncio
async def test_decisions_emitted_creates_round(
    client: AsyncClient, db: AsyncSession, mock_externals
):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="investigate", current_phase="investigate")
    phase_run = make_phase_run(pipeline, phase="investigate", status="running")
    db.add_all([ticket, pipeline, phase_run])
    await db.commit()

    decisions_payload = [
        {
            "id": "d1",
            "question": "Which approach?",
            "options": [{"key": "A", "label": "Simple"}],
            "recommendation": "A",
        },
        {
            "id": "d2",
            "question": "Which format?",
        },
    ]
    resp = await client.post(f"{INTERNAL}/decisions-emitted", json={
        "pipeline_id": str(pipeline.id),
        "phase": "investigate",
        "round_number": 1,
        "decisions": decisions_payload,
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decisions_count"] == 2
    assert "round_id" in data

    await db.refresh(pipeline)
    assert pipeline.status == "awaiting_decisions"

    await db.refresh(phase_run)
    assert phase_run.status == "awaiting_decisions"


# --- phase-completed ---


@pytest.mark.asyncio
async def test_phase_completed_dispatches_next(
    client: AsyncClient, db: AsyncSession, mock_externals
):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="investigate", current_phase="investigate")
    phase_run = make_phase_run(pipeline, phase="investigate", status="running")
    db.add_all([ticket, pipeline, phase_run])
    await db.commit()

    resp = await client.post(f"{INTERNAL}/phase-completed", json={
        "pipeline_id": str(pipeline.id),
        "phase": "investigate",
        "result": {},
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_phase"] == "refine"
    assert data["pipeline_status"] == "refine"
    mock_externals.delay.assert_called_once()


@pytest.mark.asyncio
async def test_phase_completed_final_phase_completes_pipeline(
    client: AsyncClient, db: AsyncSession, mock_externals
):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="pr", current_phase="pr")
    phase_run = make_phase_run(pipeline, phase="pr", status="running")
    db.add_all([ticket, pipeline, phase_run])
    await db.commit()

    resp = await client.post(f"{INTERNAL}/phase-completed", json={
        "pipeline_id": str(pipeline.id),
        "phase": "pr",
        "result": {"pr_url": "https://github.com/org/repo/pull/42"},
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pipeline_status"] == "completed"

    await db.refresh(pipeline)
    assert pipeline.completed_at is not None
    assert pipeline.pr_url == "https://github.com/org/repo/pull/42"
    mock_externals.delay.assert_not_called()


@pytest.mark.asyncio
async def test_phase_completed_stores_pr_url(
    client: AsyncClient, db: AsyncSession, mock_externals
):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="implement", current_phase="implement")
    phase_run = make_phase_run(pipeline, phase="implement", status="running")
    db.add_all([ticket, pipeline, phase_run])
    await db.commit()

    resp = await client.post(f"{INTERNAL}/phase-completed", json={
        "pipeline_id": str(pipeline.id),
        "phase": "implement",
        "result": {"pr_url": "https://github.com/org/repo/pull/99"},
    }, headers=HEADERS)
    assert resp.status_code == 200

    await db.refresh(pipeline)
    assert pipeline.pr_url == "https://github.com/org/repo/pull/99"


# --- phase-failed ---


@pytest.mark.asyncio
async def test_phase_failed_retries_when_safe(
    client: AsyncClient, db: AsyncSession, mock_externals
):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="investigate", current_phase="investigate")
    phase_run = make_phase_run(pipeline, phase="investigate", status="failed")
    db.add_all([ticket, pipeline, phase_run])
    await db.commit()

    resp = await client.post(f"{INTERNAL}/phase-failed", json={
        "pipeline_id": str(pipeline.id),
        "phase": "investigate",
        "error": "timeout",
        "retry_safe": True,
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "retrying"
    mock_externals.delay.assert_called_once()


@pytest.mark.asyncio
async def test_phase_failed_marks_failed_when_retries_exhausted(
    client: AsyncClient, db: AsyncSession, mock_externals
):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="investigate", current_phase="investigate")
    for _ in range(3):
        run = make_phase_run(pipeline, phase="investigate", status="failed")
        db.add(run)
    db.add_all([ticket, pipeline])
    await db.commit()

    resp = await client.post(f"{INTERNAL}/phase-failed", json={
        "pipeline_id": str(pipeline.id),
        "phase": "investigate",
        "error": "crash",
        "retry_safe": True,
    }, headers=HEADERS)
    assert resp.status_code == 200

    await db.refresh(pipeline)
    assert pipeline.status == "failed"


@pytest.mark.asyncio
async def test_phase_failed_not_retry_safe(
    client: AsyncClient, db: AsyncSession, mock_externals
):
    ticket = make_ticket()
    pipeline = make_pipeline(ticket, status="investigate", current_phase="investigate")
    db.add_all([ticket, pipeline])
    await db.commit()

    resp = await client.post(f"{INTERNAL}/phase-failed", json={
        "pipeline_id": str(pipeline.id),
        "phase": "investigate",
        "error": "bad input",
        "retry_safe": False,
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["retry_safe"] is False

    await db.refresh(pipeline)
    assert pipeline.status == "failed"


# --- progress ---


@pytest.mark.asyncio
async def test_progress_update(client: AsyncClient, mock_externals):
    resp = await client.post(f"{INTERNAL}/progress", json={
        "pipeline_id": "00000000-0000-0000-0000-000000000001",
        "phase": "investigate",
        "progress": 0.5,
        "message": "halfway there",
    }, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
