from celery import Celery
from celery.schedules import crontab

from ..config import settings

app = Celery("pylon", broker=settings.redis_url, backend=settings.redis_url)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/New_York",
    enable_utc=True,
    worker_concurrency=settings.max_workers,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=86400,
)

app.conf.beat_schedule = {
    "poll-asana": {
        "task": "src.pylon.tasks.asana.poll_asana",
        "schedule": settings.asana_poll_interval_seconds,
    },
    "detect-stale-workers": {
        "task": "src.pylon.tasks.maintenance.detect_stale_workers",
        "schedule": 300,
    },
    "overnight-batch": {
        "task": "src.pylon.tasks.pipeline.overnight_batch",
        "schedule": crontab(hour=23, minute=0),
    },
}

app.autodiscover_tasks(["src.pylon.tasks"])
