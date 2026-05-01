import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from celery import chord
from celery.exceptions import SoftTimeLimitExceeded

from ..config import settings
from ..harness.ipc import read_result, read_round_file, write_answers_file, write_config
from ..harness.worker import kill_worker, spawn_worker
from .celery_app import app

PHASE_ORDER = ["investigate", "refine", "plan", "critique", "implement", "test", "pr"]


@app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=2700,
    time_limit=3000,
    acks_late=True,
)
def run_phase(self, pipeline_id: str, phase: str, round_answers: dict | None = None):
    timeout = settings.phase_timeouts.get(phase, 1800)

    try:
        result = asyncio.run(_run_phase(pipeline_id, phase, timeout, round_answers))
    except SoftTimeLimitExceeded:
        asyncio.run(_handle_timeout(pipeline_id, phase))
        return {"status": "timed_out", "phase": phase}

    return result


async def _run_phase(
    pipeline_id: str,
    phase: str,
    timeout: int,
    round_answers: dict | None = None,
):
    notes_path = Path(settings.notes_base_path) / pipeline_id
    pylon_dir = notes_path / ".pylon"
    pylon_dir.mkdir(parents=True, exist_ok=True)

    write_config(pylon_dir, pipeline_id, phase)

    if round_answers:
        round_num = round_answers.get("round", 1)
        write_answers_file(pylon_dir, round_num, round_answers)

    proc = await spawn_worker(
        pipeline_id=pipeline_id,
        phase=phase,
        notes_path=str(notes_path),
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        await kill_worker(proc)
        return {"status": "timed_out", "phase": phase}

    if proc.returncode != 0:
        error = stderr.decode() if stderr else "unknown error"
        if "Rate limit" in error:
            raise run_phase.retry(countdown=120)
        return {"status": "failed", "phase": phase, "error": error}

    result = read_result(pylon_dir)
    if not result:
        return {"status": "failed", "phase": phase, "error": "no result.json produced"}

    if result.get("status") == "awaiting_decisions":
        round_file = read_round_file(pylon_dir, result.get("round", 1))
        # TODO: POST decisions to internal API
        return {"status": "awaiting_decisions", "round": result.get("round")}

    if result.get("status") == "complete":
        # TODO: POST phase-completed to internal API
        phase_idx = PHASE_ORDER.index(phase) if phase in PHASE_ORDER else -1
        if phase_idx < len(PHASE_ORDER) - 1:
            next_phase = PHASE_ORDER[phase_idx + 1]
            if next_phase not in ("refine", "critique"):
                run_phase.delay(pipeline_id, next_phase)
        return {"status": "complete", "phase": phase}

    return result


async def _handle_timeout(pipeline_id: str, phase: str):
    # TODO: POST phase-failed to internal API with timeout error
    pass


@app.task
def overnight_batch():
    # TODO: poll Asana for ready tickets, group by assignee, dispatch investigations
    # chord(
    #     [run_phase.s(pid, "investigate") for pid in pipeline_ids],
    #     notify_batch_complete.s()
    # )()
    pass


@app.task
def notify_batch_complete(results):
    # TODO: send Slack notification summarizing completed investigations
    pass
