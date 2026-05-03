import asyncio
import json
import signal
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.pylon.harness.worker import (
    acquire_account,
    kill_worker,
    monitor_decisions,
    release_worker,
)
from src.pylon.models import WorkerSession
from tests.factories import make_pipeline, make_ticket

MOD = "src.pylon.harness.worker"


@pytest.fixture
async def db_with_pipeline(db):
    ticket = make_ticket()
    db.add(ticket)
    pipeline = make_pipeline(ticket)
    db.add(pipeline)
    await db.commit()
    return db, pipeline


@pytest.fixture
def patch_session(db_with_pipeline):
    db, pipeline = db_with_pipeline
    factory = async_sessionmaker(bind=db.get_bind(), class_=type(db), expire_on_commit=False)
    with patch(f"{MOD}.async_session", factory):
        yield db, pipeline


# --- acquire_account ---


async def test_acquire_account_returns_first_available(setup_db):
    factory = async_sessionmaker(setup_db, expire_on_commit=False)

    async with factory() as session:
        ticket = make_ticket()
        session.add(ticket)
        pipeline = make_pipeline(ticket)
        session.add(pipeline)
        await session.commit()
        pipeline_id = pipeline.id

    with patch(f"{MOD}.async_session", factory):
        result = await acquire_account(str(pipeline_id), "investigate", 1200)

    assert result is not None
    assert result.account == "default"
    assert result.status == "starting"


async def test_acquire_account_skips_active(setup_db):
    factory = async_sessionmaker(setup_db, expire_on_commit=False)

    async with factory() as session:
        t1, t2 = make_ticket(), make_ticket()
        session.add_all([t1, t2])
        p1 = make_pipeline(t1)
        p2 = make_pipeline(t2)
        session.add_all([p1, p2])
        await session.commit()
        p1_id, p2_id = p1.id, p2.id

    with patch(f"{MOD}.async_session", factory):
        s1 = await acquire_account(str(p1_id), "investigate", 1200)
        s2 = await acquire_account(str(p2_id), "investigate", 1200)

    assert s1.account != s2.account


async def test_acquire_account_returns_none_when_full(setup_db):
    factory = async_sessionmaker(setup_db, expire_on_commit=False)

    async with factory() as session:
        tickets = [make_ticket() for _ in range(4)]
        session.add_all(tickets)
        pipelines = [make_pipeline(t) for t in tickets]
        session.add_all(pipelines)
        await session.commit()
        ids = [p.id for p in pipelines]

    with patch(f"{MOD}.async_session", factory):
        for i in range(3):
            await acquire_account(str(ids[i]), "investigate", 1200)
        result = await acquire_account(str(ids[3]), "investigate", 1200)

    assert result is None


# --- release_worker ---


async def test_release_worker_sets_completed(setup_db):
    factory = async_sessionmaker(setup_db, expire_on_commit=False)

    async with factory() as session:
        ticket = make_ticket()
        session.add(ticket)
        pipeline = make_pipeline(ticket)
        session.add(pipeline)
        await session.commit()
        pipeline_id = pipeline.id

    with patch(f"{MOD}.async_session", factory):
        ws = await acquire_account(str(pipeline_id), "investigate", 1200)
        await release_worker(ws.id, exit_code=0)

    async with factory() as session:
        result = await session.execute(
            select(WorkerSession).where(WorkerSession.id == ws.id)
        )
        updated = result.scalar_one()
        assert updated.status == "completed"
        assert updated.exit_code == 0
        assert updated.completed_at is not None


async def test_release_worker_sets_failed_with_error(setup_db):
    factory = async_sessionmaker(setup_db, expire_on_commit=False)

    async with factory() as session:
        ticket = make_ticket()
        session.add(ticket)
        pipeline = make_pipeline(ticket)
        session.add(pipeline)
        await session.commit()
        pipeline_id = pipeline.id

    with patch(f"{MOD}.async_session", factory):
        ws = await acquire_account(str(pipeline_id), "investigate", 1200)
        await release_worker(ws.id, exit_code=1, error="timeout exceeded")

    async with factory() as session:
        result = await session.execute(
            select(WorkerSession).where(WorkerSession.id == ws.id)
        )
        updated = result.scalar_one()
        assert updated.status == "failed"
        assert updated.exit_code == 1
        assert updated.error_output == "timeout exceeded"


# --- monitor_decisions ---


async def test_monitor_detects_round_file(tmp_path):
    pylon_dir = tmp_path / ".pylon"
    decisions_dir = pylon_dir / "decisions"
    decisions_dir.mkdir(parents=True)

    notify = AsyncMock()
    proc = MagicMock()
    proc.returncode = None

    async def write_round_after_delay():
        await asyncio.sleep(0.05)
        (decisions_dir / "round-1.json").write_text(json.dumps({
            "decisions": [{"id": "d1", "question": "Test?", "options": []}]
        }))
        await asyncio.sleep(0.05)
        proc.returncode = 0

    with patch(f"{MOD}.DECISION_POLL_INTERVAL", 0.02):
        asyncio.create_task(write_round_after_delay())
        reported = await monitor_decisions(pylon_dir, "pipe-1", "refine", proc, notify)

    assert 1 in reported
    notify.assert_called_once()
    call_args = notify.call_args[0]
    assert call_args[0] == "decisions-emitted"
    assert call_args[1]["round_number"] == 1


async def test_monitor_skips_rounds_with_answers(tmp_path):
    pylon_dir = tmp_path / ".pylon"
    decisions_dir = pylon_dir / "decisions"
    decisions_dir.mkdir(parents=True)

    (decisions_dir / "round-1.json").write_text(json.dumps({
        "decisions": [{"id": "d1", "question": "Q?", "options": []}]
    }))
    (decisions_dir / "round-1-answers.json").write_text(json.dumps({
        "answers": {"d1": "A"}
    }))

    notify = AsyncMock()
    proc = MagicMock()
    proc.returncode = None

    async def stop_proc():
        await asyncio.sleep(0.05)
        proc.returncode = 0

    with patch(f"{MOD}.DECISION_POLL_INTERVAL", 0.02):
        asyncio.create_task(stop_proc())
        reported = await monitor_decisions(pylon_dir, "pipe-1", "refine", proc, notify)

    assert reported == []
    notify.assert_not_called()


# --- kill_worker ---


async def test_kill_worker_sends_sigterm_then_waits():
    proc = AsyncMock()
    proc.returncode = None
    proc.send_signal = MagicMock()
    proc.wait = AsyncMock(return_value=0)

    await kill_worker(proc, grace_period=5)

    proc.send_signal.assert_called_once_with(signal.SIGTERM)
    proc.wait.assert_called_once()


async def test_kill_worker_escalates_to_sigkill():
    proc = AsyncMock()
    proc.returncode = None
    proc.send_signal = MagicMock()
    proc.wait = AsyncMock(side_effect=asyncio.TimeoutError)
    proc.kill = MagicMock()

    post_kill_wait = AsyncMock(return_value=0)

    call_count = 0

    async def wait_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.TimeoutError
        return 0

    proc.wait = AsyncMock(side_effect=wait_side_effect)

    await kill_worker(proc, grace_period=1)

    proc.send_signal.assert_called_once_with(signal.SIGTERM)
    proc.kill.assert_called_once()


async def test_kill_worker_noop_if_already_exited():
    proc = AsyncMock()
    proc.returncode = 0
    proc.send_signal = MagicMock()

    await kill_worker(proc)

    proc.send_signal.assert_not_called()
