import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from celery import chord
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from ..config import settings
from ..database import async_session
from ..harness.ipc import read_result, read_round_file, write_answers_file, write_config
from ..harness.preinvestigate import run_pre_investigation
from ..harness.worker import kill_worker, spawn_worker
from ..models import Pipeline, Ticket
from .celery_app import app

logger = logging.getLogger(__name__)

PHASE_ORDER = ["investigate", "refine", "plan", "critique", "implement", "test", "pr"]


async def _notify_internal(endpoint: str, payload: dict) -> dict:
    url = f"{settings.api_base_url}/api/internal/{endpoint}"
    headers = {"x-pylon-key": settings.pylon_internal_key}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()


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

    await _notify_internal("phase-started", {
        "pipeline_id": pipeline_id,
        "phase": phase,
        "worker_id": None,
    })

    # Pre-investigation: run zero-token static analysis before Claude sees the code
    if phase == "investigate":
        repo_path = _resolve_repo_path(pipeline_id)
        if repo_path:
            keywords = _extract_keywords(notes_path)
            await run_pre_investigation(
                repo_path=repo_path,
                notes_path=str(notes_path),
                keywords=keywords,
            )

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
        await _notify_internal("phase-failed", {
            "pipeline_id": pipeline_id,
            "phase": phase,
            "error": error,
            "retry_safe": True,
        })
        return {"status": "failed", "phase": phase, "error": error}

    result = read_result(pylon_dir)
    if not result:
        await _notify_internal("phase-failed", {
            "pipeline_id": pipeline_id,
            "phase": phase,
            "error": "no result.json produced",
            "retry_safe": True,
        })
        return {"status": "failed", "phase": phase, "error": "no result.json produced"}

    if result.get("status") == "awaiting_decisions":
        round_num = result.get("round", 1)
        round_file = read_round_file(pylon_dir, round_num)
        if round_file:
            await _notify_internal("decisions-emitted", {
                "pipeline_id": pipeline_id,
                "phase": phase,
                "round_number": round_num,
                "decisions": round_file.get("decisions", []),
            })
        return {"status": "awaiting_decisions", "round": round_num}

    if result.get("status") == "complete":
        await _notify_internal("phase-completed", {
            "pipeline_id": pipeline_id,
            "phase": phase,
            "result": result,
        })
        return {"status": "complete", "phase": phase}

    return result


async def _handle_timeout(pipeline_id: str, phase: str):
    await _notify_internal("phase-failed", {
        "pipeline_id": pipeline_id,
        "phase": phase,
        "error": "phase timed out (soft limit exceeded)",
        "retry_safe": True,
    })


@app.task
def overnight_batch():
    return asyncio.run(_overnight_batch())


async def _overnight_batch():
    async with async_session() as db:
        result = await db.execute(
            select(Pipeline)
            .join(Ticket)
            .where(Pipeline.status == "queued", Pipeline.started_at.is_(None))
            .order_by(Ticket.priority.desc().nulls_last(), Pipeline.created_at)
            .limit(settings.max_tickets_per_batch)
        )
        pipelines = result.scalars().all()

    if not pipelines:
        return {"dispatched": 0}

    pipeline_ids = [str(p.id) for p in pipelines]

    chord(
        [run_phase.s(pid, "investigate") for pid in pipeline_ids],
        notify_batch_complete.s(pipeline_ids),
    )()

    logger.info("overnight_batch dispatched %d pipelines", len(pipeline_ids))
    return {"dispatched": len(pipeline_ids), "pipeline_ids": pipeline_ids}


@app.task
def notify_batch_complete(results, pipeline_ids):
    if not settings.slack_webhook_url:
        return {"skipped": "slack not configured"}

    return asyncio.run(_notify_batch_complete(results, pipeline_ids))


async def _notify_batch_complete(results, pipeline_ids):
    succeeded = sum(1 for r in results if r and r.get("status") == "complete")
    awaiting = sum(1 for r in results if r and r.get("status") == "awaiting_decisions")
    failed = len(results) - succeeded - awaiting

    lines = [
        f"*Overnight batch complete* ({len(results)} pipelines)",
        f"  Investigated: {succeeded}  |  Awaiting decisions: {awaiting}  |  Failed: {failed}",
    ]

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            settings.slack_webhook_url,
            json={"text": "\n".join(lines)},
        )

    return {"notified": True, "succeeded": succeeded, "awaiting": awaiting, "failed": failed}


def _resolve_repo_path(pipeline_id: str) -> str | None:
    """Look up the repo path for a pipeline. Returns None if not determinable."""
    # TODO: query DB for pipeline -> ticket -> repo, resolve to filesystem path
    # e.g. settings.repos_base_path / ticket.repo
    return None


def _extract_keywords(notes_path: Path) -> list[str]:
    """Pull keywords from ticket context for targeted ripgrep search."""
    config_file = notes_path / ".pylon" / "config.json"
    if not config_file.exists():
        return []
    import json
    config = json.loads(config_file.read_text())
    context = config.get("context", "")
    # Split context into meaningful search terms
    words = [w for w in context.split() if len(w) > 4 and w.isalpha()]
    return words[:10]
