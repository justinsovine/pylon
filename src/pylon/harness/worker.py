import asyncio
import logging
import os
import signal
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from ..config import settings
from ..database import async_session
from ..models import WorkerSession

logger = logging.getLogger(__name__)


async def acquire_account(pipeline_id: str, phase: str, timeout: int) -> WorkerSession | None:
    async with async_session() as db:
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

        if not available:
            return None

        session = WorkerSession(
            pipeline_id=pipeline_id,
            phase=phase,
            account=available,
            status="starting",
            started_at=datetime.utcnow(),
            timeout_seconds=timeout,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session


async def mark_worker_running(session_id, pid: int):
    async with async_session() as db:
        result = await db.execute(
            select(WorkerSession).where(WorkerSession.id == session_id)
        )
        session = result.scalar_one()
        session.status = "running"
        session.pid = pid
        await db.commit()


async def release_worker(session_id, exit_code: int | None = None, error: str | None = None):
    async with async_session() as db:
        result = await db.execute(
            select(WorkerSession).where(WorkerSession.id == session_id)
        )
        session = result.scalar_one()
        session.status = "completed" if exit_code == 0 else "failed"
        session.completed_at = datetime.utcnow()
        session.exit_code = exit_code
        if error:
            session.error_output = error[:2000]
        await db.commit()


async def spawn_worker(
    pipeline_id: str,
    phase: str,
    notes_path: str,
    account: str | None = None,
    worktree_path: Path | None = None,
    asana_gid: str | None = None,
    answers_file: str | None = None,
) -> asyncio.subprocess.Process:
    prompt = f"/pylon {phase} --notes={notes_path}"
    if asana_gid:
        prompt += f" --asana={asana_gid}"
    if answers_file:
        prompt += f" --decisions={answers_file}"

    env = {
        **os.environ,
        "PYLON_WORKER": "true",
        "PYLON_PIPELINE_ID": pipeline_id,
        "PYLON_PHASE": phase,
        "PYLON_NOTES_PATH": notes_path,
        "PYLON_API_URL": settings.api_base_url,
        "PYLON_API_KEY": settings.pylon_internal_key,
    }
    if account:
        env["PYLON_ACCOUNT"] = account

    cwd = str(worktree_path) if worktree_path and worktree_path.exists() else None

    proc = await asyncio.create_subprocess_exec(
        "claude",
        "-p",
        prompt,
        "--output-format",
        "text",
        env=env,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    return proc


async def kill_worker(proc: asyncio.subprocess.Process, grace_period: int = 30):
    if proc.returncode is not None:
        return

    proc.send_signal(signal.SIGTERM)

    try:
        await asyncio.wait_for(proc.wait(), timeout=grace_period)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def create_worktree(
    repo_path: str,
    pipeline_id: str,
    branch_name: str,
) -> Path:
    worktree_path = Path(settings.worktrees_path) / pipeline_id
    if worktree_path.exists():
        logger.info("Worktree already exists at %s", worktree_path)
        return worktree_path

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    branch_exists = await _branch_exists(repo_path, branch_name)

    if branch_exists:
        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "add", str(worktree_path), branch_name,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "add", "-b", branch_name, str(worktree_path), "HEAD",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        error = stderr.decode().strip()
        raise RuntimeError(f"git worktree add failed: {error}")

    logger.info("Created worktree at %s (branch %s)", worktree_path, branch_name)
    return worktree_path


async def remove_worktree(repo_path: str, pipeline_id: str) -> None:
    worktree_path = Path(settings.worktrees_path) / pipeline_id
    if not worktree_path.exists():
        return

    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "remove", "--force", str(worktree_path),
        cwd=repo_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    logger.info("Removed worktree at %s", worktree_path)


async def _branch_exists(repo_path: str, branch_name: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "git", "rev-parse", "--verify", f"refs/heads/{branch_name}",
        cwd=repo_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    return proc.returncode == 0
