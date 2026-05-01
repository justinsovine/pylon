import asyncio
import os
import signal
from pathlib import Path

from ..config import settings

ACCOUNTS = ["default", "worker-a", "worker-b"]
_active_accounts: set[str] = set()


def get_available_account() -> str | None:
    for account in ACCOUNTS:
        if account not in _active_accounts:
            return account
    return None


async def spawn_worker(
    pipeline_id: str,
    phase: str,
    notes_path: str,
    asana_gid: str | None = None,
    answers_file: str | None = None,
) -> asyncio.subprocess.Process:
    account = get_available_account()
    if account:
        _active_accounts.add(account)

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
        "PYLON_API_URL": f"http://localhost:8000",
        "PYLON_API_KEY": settings.pylon_internal_key,
    }

    worktree_path = Path(settings.worktrees_path) / pipeline_id

    proc = await asyncio.create_subprocess_exec(
        "claude",
        "-p",
        prompt,
        "--output-format",
        "text",
        env=env,
        cwd=str(worktree_path) if worktree_path.exists() else None,
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


def release_account(account: str):
    _active_accounts.discard(account)
