import psutil

from .celery_app import app


@app.task
def detect_stale_workers():
    # TODO: query worker_sessions where status in (running, waiting)
    # and started_at < now() - 2 hours
    # For each: check if PID exists, mark failed if not
    pass


@app.task
def cleanup_worktrees():
    # TODO: for completed/cancelled pipelines older than 7 days,
    # remove git worktrees
    pass
