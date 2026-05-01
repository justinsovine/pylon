# Pylon -- Worker Lifecycle

## What a worker is

A worker is a single Claude Code CLI process executing one phase of one ticket. It runs in its own git worktree, reads/writes to the shared notes directory, and communicates with Pylon through files in .pylon/.

Workers are ephemeral. They start, do work, and exit. No long-lived sessions.

## Worker states

```
           ┌──────────┐
           │ spawning │
           └────┬─────┘
                │ process started
           ┌────▼─────┐
           │ running  │
           └────┬─────┘
                │
        ┌───────┼────────┐
        │       │        │
   ┌────▼──┐ ┌─▼────┐ ┌─▼──────┐
   │parked │ │done  │ │failed  │
   └───┬───┘ └──────┘ └────┬───┘
       │                    │
       │ answers arrive     │ retry?
       │                    │
  ┌────▼─────┐         ┌───▼──────┐
  │ resuming │         │ retrying │
  └────┬─────┘         └───┬──────┘
       │                    │
       ▼                    ▼
    (new worker)         (new worker)
```

"Resuming" and "retrying" both spawn a new Claude Code process. The distinction is whether the previous run produced partial results (parked with decisions) or failed.

## Spawn

### Celery task definition

```python
@app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=1800,   # 30 min soft limit (raises SoftTimeLimitExceeded)
    time_limit=2100,        # 35 min hard kill
    acks_late=True,         # don't ack until complete (survives worker restart)
)
def run_phase(self, pipeline_id, phase, pass_number=1, round_answers=None):
    ...
```

### Pre-spawn checklist

Before spawning Claude Code:

1. **Worktree exists?** Create if not: `git worktree add worktrees/ticket-slug feature/ticket-slug`
2. **Branch exists?** Create if not: `git checkout -b feature/ticket-slug`
3. **Notes directory exists?** Create if not.
4. **.pylon/config.json written?** Write pipeline metadata.
5. **Prior phase complete?** Check phase_runs table.
6. **No other worker running for this pipeline?** Prevent double-spawn.

### Claude Code invocation

```python
import asyncio

async def spawn_worker(pipeline, phase, pass_number, answers_file=None):
    env = {
        **os.environ,
        "PYLON_WORKER": "true",
        "PYLON_PIPELINE_ID": str(pipeline.id),
        "PYLON_PHASE": phase,
        "PYLON_NOTES_PATH": pipeline.notes_path,
    }
    
    prompt = f"/feature {phase} --notes={pipeline.notes_path}"
    if pipeline.asana_gid:
        prompt += f" --asana={pipeline.asana_gid}"
    if answers_file:
        prompt += f" --decisions={answers_file}"
    
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--output-format", "text",
        env=env,
        cwd=pipeline.worktree_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    return proc
```

### Account rotation

With 3 Claude accounts, workers rotate:

```python
ACCOUNTS = ["default", "worker-a", "worker-b"]

def get_next_account():
    # Simple round-robin, or least-recently-used
    active = get_active_worker_accounts()
    for account in ACCOUNTS:
        if account not in active:
            return account
    # All busy -- queue the task
    return None
```

Account selection happens at spawn time. If all accounts are busy, Celery task stays in queue until one frees up. Celery's `worker_concurrency=3` enforces this naturally.

## Monitor

### Health checks (every 30 seconds)

```python
async def health_check(worker_session):
    # 1. Process still alive?
    if not pid_exists(worker_session.pid):
        mark_failed(worker_session, "Process died unexpectedly")
        return
    
    # 2. Status file updating?
    status = read_status_json(worker_session)
    if status and status.updated_at < now() - timedelta(minutes=10):
        # Stale. Claude Code might be hung.
        log_warning(f"Worker {worker_session.id} stale for 10+ minutes")
    
    # 3. Decision file appeared?
    round_file = find_new_round_file(worker_session)
    if round_file:
        handle_decision_round(worker_session, round_file)
    
    # 4. Result file appeared?
    result = read_result_json(worker_session)
    if result:
        handle_phase_complete(worker_session, result)
```

### Progress tracking

Workers update .pylon/status.json periodically. The harness polls this file and updates the database. Dashboard reads from database.

Progress is approximate. Phases don't have predictable durations. Status messages ("Reading investigation notes", "Analyzing 34 route files", "Generating stage 3 of 5") are more useful than percentages.

## Timeout

### Soft timeout (Celery soft_time_limit)

Raises `SoftTimeLimitExceeded` in the Celery task. Task catches it, sends SIGTERM to Claude Code process, waits 30 seconds for graceful shutdown, then SIGKILL.

```python
from celery.exceptions import SoftTimeLimitExceeded

@app.task(bind=True, soft_time_limit=1800, time_limit=2100)
def run_phase(self, pipeline_id, phase, **kwargs):
    try:
        result = await spawn_and_monitor(pipeline_id, phase, **kwargs)
    except SoftTimeLimitExceeded:
        kill_worker_gracefully(pipeline_id)
        mark_phase_timed_out(pipeline_id, phase)
        # Don't auto-retry timeouts -- likely a real problem
        notify_dev(pipeline_id, f"{phase} timed out after 30 minutes")
```

### Per-phase timeout defaults

| Phase | Default timeout | Rationale |
|-------|----------------|-----------|
| investigate | 20 min | Reading code, no generation |
| refine | 10 min | Analysis only, no code changes |
| plan | 15 min | Generating plan document |
| critique | 10 min | Reviewing existing plan |
| implement | 45 min | Writing code, running tests per stage |
| test | 20 min | Writing and running tests |
| pr | 10 min | Diff cleanup, description writing |

Configurable per-ticket via dashboard (big features get longer timeouts).

## Retry

### Automatic retry conditions

- Exit code 1 + stderr contains "Rate limit" -> retry after 120 seconds
- Exit code 1 + stderr contains "Connection" -> retry after 60 seconds
- Process killed by OOM -> retry on different worker

### No automatic retry

- Exit code 0 + result.json status = "failed" (Claude Code ran but couldn't complete)
- Timeout (likely a real problem, not transient)
- Exit code 1 + no recognizable error pattern

### Retry mechanics

```python
@app.task(bind=True, max_retries=2)
def run_phase(self, pipeline_id, phase, **kwargs):
    try:
        result = await spawn_and_monitor(pipeline_id, phase, **kwargs)
    except RateLimitError:
        raise self.retry(countdown=120)
    except ConnectionError:
        raise self.retry(countdown=60)
```

Each retry creates a new worker_session row. phase_run stays the same (it's the same attempt at the phase, just retried).

### Manual retry

Dev clicks "Retry" in dashboard. Creates new Celery task. New worker_session. Same phase_run if re-entering, new phase_run if starting fresh.

## Cleanup

### After successful phase completion

1. Update phase_run status = completed
2. Update pipeline current_phase to next phase
3. Worker session marked completed
4. Trigger next phase (if non-decision phase) or wait (if decision phase)
5. Worktree stays (needed for subsequent phases on same ticket)

### After pipeline completion (PR opened)

1. Worktree cleaned up: `git worktree remove worktrees/ticket-slug`
2. Branch stays (it's the PR branch)
3. Notes directory stays (audit trail)
4. Worker sessions stay in DB (audit trail)
5. .pylon/ directory archived or cleaned after PR merge

### Stale worker detection

Celery beat task runs every 5 minutes:

```python
@app.task
def detect_stale_workers():
    stale = WorkerSession.query.filter(
        WorkerSession.status.in_(['running', 'waiting']),
        WorkerSession.started_at < now() - timedelta(hours=2)
    ).all()
    
    for worker in stale:
        if not pid_exists(worker.pid):
            mark_failed(worker, "Process disappeared (stale detection)")
            notify_dev(worker.pipeline_id, "Worker died silently")
```

## Concurrency rules

- Max 1 active worker per pipeline (no two phases of the same ticket run simultaneously)
- Max 3 total active workers (one per Claude account)
- Max 2 workers per repo (prevent worktree conflicts on shared files)
- Implement phase gets exclusive repo access (it writes code, others just read)

These are enforced at task dispatch, not process level. Celery task checks constraints before spawning.
