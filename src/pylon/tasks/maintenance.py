import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

import psutil
from sqlalchemy import select

from ..config import settings
from ..database import async_session
from ..models import Pipeline, WorkerSession
from .celery_app import app

logger = logging.getLogger(__name__)


@app.task
def detect_stale_workers():
    return asyncio.run(_detect_stale_workers())


async def _detect_stale_workers():
    async with async_session() as db:
        result = await db.execute(
            select(WorkerSession).where(
                WorkerSession.status.in_(["starting", "running"])
            )
        )
        active_workers = result.scalars().all()

    if not active_workers:
        return {"checked": 0, "killed": 0, "reaped": 0}

    killed = 0
    reaped = 0
    now = datetime.utcnow()

    for worker in active_workers:
        pid_alive = worker.pid and psutil.pid_exists(worker.pid)
        timed_out = (
            worker.started_at
            and (now - worker.started_at).total_seconds() > worker.timeout_seconds
        )

        if not pid_alive:
            await _mark_worker_failed(
                worker.id, "process not found (PID gone)"
            )
            reaped += 1
            logger.warning(
                "Reaped dead worker %s (pipeline=%s, phase=%s, pid=%s)",
                worker.id, worker.pipeline_id, worker.phase, worker.pid,
            )
            continue

        if timed_out:
            try:
                proc = psutil.Process(worker.pid)
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except psutil.TimeoutExpired:
                    proc.kill()
            except psutil.NoSuchProcess:
                pass

            await _mark_worker_failed(
                worker.id,
                f"killed: exceeded timeout ({worker.timeout_seconds}s)",
            )
            killed += 1
            logger.warning(
                "Killed stuck worker %s (pipeline=%s, phase=%s, ran %ds)",
                worker.id, worker.pipeline_id, worker.phase,
                int((now - worker.started_at).total_seconds()),
            )

    logger.info(
        "Worker health check: %d active, %d reaped, %d killed",
        len(active_workers), reaped, killed,
    )
    return {"checked": len(active_workers), "killed": killed, "reaped": reaped}


async def _mark_worker_failed(worker_id, error: str):
    async with async_session() as db:
        result = await db.execute(
            select(WorkerSession).where(WorkerSession.id == worker_id)
        )
        worker = result.scalar_one()
        worker.status = "failed"
        worker.completed_at = datetime.utcnow()
        worker.error_output = error[:2000]
        await db.commit()


@app.task
def cleanup_worktrees():
    return asyncio.run(_cleanup_worktrees())


async def _cleanup_worktrees():
    cutoff = datetime.utcnow() - timedelta(days=7)

    async with async_session() as db:
        result = await db.execute(
            select(Pipeline).where(
                Pipeline.status.in_(["completed", "cancelled", "failed"]),
                Pipeline.completed_at < cutoff,
            )
        )
        old_pipelines = result.scalars().all()

    if not old_pipelines:
        return {"cleaned": 0}

    cleaned = 0
    for pipeline in old_pipelines:
        worktree_path = Path(settings.worktrees_path) / str(pipeline.id)
        if not worktree_path.exists():
            continue

        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "remove", "--force", str(worktree_path),
            cwd=settings.repos_base_path or ".",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        cleaned += 1
        logger.info("Cleaned worktree for pipeline %s", pipeline.id)

    return {"cleaned": cleaned}
