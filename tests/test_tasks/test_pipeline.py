import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.pylon.tasks.pipeline import _overnight_batch, _run_phase
from tests.factories import make_pipeline, make_ticket

MOD = "src.pylon.tasks.pipeline"


def _fake_worker_session(pipeline_id="x", account="acct-1"):
    ws = MagicMock()
    ws.id = uuid.uuid4()
    ws.account = account
    return ws


@pytest.fixture
def phase_mocks(tmp_path):
    pipeline_id = str(uuid.uuid4())
    proc = MagicMock(returncode=0, pid=12345)
    ws = _fake_worker_session(pipeline_id)

    with (
        patch(f"{MOD}._notify_internal", new_callable=AsyncMock) as notify,
        patch(f"{MOD}._get_pipeline_info", new_callable=AsyncMock) as info,
        patch(f"{MOD}._resolve_repo_path", new_callable=AsyncMock) as repo,
        patch(f"{MOD}.create_worktree", new_callable=AsyncMock),
        patch(f"{MOD}.run_pre_investigation", new_callable=AsyncMock) as preinv,
        patch(f"{MOD}.acquire_account", new_callable=AsyncMock) as acquire,
        patch(f"{MOD}.spawn_worker", new_callable=AsyncMock) as spawn,
        patch(f"{MOD}.mark_worker_running", new_callable=AsyncMock),
        patch(f"{MOD}.run_worker_with_monitor", new_callable=AsyncMock) as monitor,
        patch(f"{MOD}.release_worker", new_callable=AsyncMock),
        patch(f"{MOD}.read_result") as read_result,
        patch(f"{MOD}.read_round_file"),
        patch(f"{MOD}.write_config"),
        patch(f"{MOD}.write_ticket_context"),
        patch(f"{MOD}.write_answers_file"),
        patch(f"{MOD}.settings") as settings,
        patch(f"{MOD}.run_phase") as task,
    ):
        settings.notes_base_path = str(tmp_path / "notes")
        settings.phase_timeouts = {}
        info.return_value = {
            "repo": "onboard",
            "branch_name": "pylon/test",
            "slug": "test",
            "ticket": {
                "title": "T",
                "description": "d",
                "assignee": "j",
                "repo": "onboard",
                "priority": "high",
                "asana_gid": "1",
            },
        }
        repo.return_value = str(tmp_path / "repos" / "onboard")
        acquire.return_value = ws
        spawn.return_value = proc
        monitor.return_value = (b"ok", b"", [])
        read_result.return_value = {"status": "complete"}

        yield {
            "notify": notify,
            "preinv": preinv,
            "proc": proc,
            "monitor": monitor,
            "read_result": read_result,
            "task": task,
            "pipeline_id": pipeline_id,
        }


async def test_run_phase_calls_started_notification(phase_mocks):
    m = phase_mocks
    await _run_phase(m["pipeline_id"], "investigate", 1800)
    m["notify"].assert_any_call(
        "phase-started",
        {"pipeline_id": m["pipeline_id"], "phase": "investigate", "worker_id": None},
    )


async def test_run_phase_investigate_triggers_pre_investigation(phase_mocks):
    await _run_phase(phase_mocks["pipeline_id"], "investigate", 1800)
    phase_mocks["preinv"].assert_called_once()


async def test_run_phase_non_investigate_skips_pre_investigation(phase_mocks):
    await _run_phase(phase_mocks["pipeline_id"], "plan", 1800)
    phase_mocks["preinv"].assert_not_called()


async def test_run_phase_success_notifies_completed(phase_mocks):
    m = phase_mocks
    result = await _run_phase(m["pipeline_id"], "investigate", 1800)
    assert result == {"status": "complete", "phase": "investigate"}
    m["notify"].assert_any_call(
        "phase-completed",
        {
            "pipeline_id": m["pipeline_id"],
            "phase": "investigate",
            "result": {"status": "complete"},
        },
    )


async def test_run_phase_worker_failure_notifies_failed(phase_mocks):
    m = phase_mocks
    m["proc"].returncode = 1
    m["monitor"].return_value = (b"", b"some error", [])
    result = await _run_phase(m["pipeline_id"], "investigate", 1800)
    assert result["status"] == "failed"
    m["notify"].assert_any_call(
        "phase-failed",
        {
            "pipeline_id": m["pipeline_id"],
            "phase": "investigate",
            "error": "some error",
            "retry_safe": True,
        },
    )


async def test_run_phase_rate_limit_retries(phase_mocks):
    m = phase_mocks
    m["proc"].returncode = 1
    m["monitor"].return_value = (b"", b"Rate limit exceeded", [])
    m["task"].retry.side_effect = Exception("retry")
    with pytest.raises(Exception, match="retry"):
        await _run_phase(m["pipeline_id"], "investigate", 1800)
    m["task"].retry.assert_called_once_with(countdown=120)


async def test_overnight_batch_dispatches_queued_pipelines(db, setup_db):
    t1 = make_ticket()
    t2 = make_ticket()
    t3 = make_ticket()
    db.add_all([t1, t2, t3])
    await db.flush()

    p1 = make_pipeline(t1, status="queued")
    p2 = make_pipeline(t2, status="queued")
    p3 = make_pipeline(t3, status="running")
    db.add_all([p1, p2, p3])
    await db.commit()

    factory = async_sessionmaker(setup_db, class_=AsyncSession, expire_on_commit=False)
    with (
        patch(f"{MOD}.async_session", factory),
        patch(f"{MOD}.chord") as mock_chord,
        patch(f"{MOD}.settings") as mock_settings,
    ):
        mock_settings.max_tickets_per_batch = 10
        mock_chord.return_value = MagicMock()
        result = await _overnight_batch()

    assert result["dispatched"] == 2
    assert len(result["pipeline_ids"]) == 2
    mock_chord.assert_called_once()
