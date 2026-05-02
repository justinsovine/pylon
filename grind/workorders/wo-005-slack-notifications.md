# WO-005: Slack webhook notifications

## Scope
Slack notifications on decisions-emitted, phase-failed, pipeline-completed. Small.

## Files to read
- src/pylon/api/internal.py (lines 74-124: decisions_emitted, lines 127-170: phase_completed, lines 173-221: phase_failed)
- src/pylon/config.py (line 14: slack_webhook_url)
- src/pylon/tasks/pipeline.py (lines 225-241: existing _notify_batch_complete pattern)

## Key context

Existing Slack pattern in pipeline.py (lines 230-241):
```python
async def _notify_batch_complete(results, pipeline_ids):
    succeeded = sum(1 for r in results if r and r.get("status") == "complete")
    lines = [
        f"*Overnight batch complete* ({len(results)} pipelines)",
        f"  Investigated: {succeeded}  |  Awaiting decisions: {awaiting}  |  Failed: {failed}",
    ]
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(settings.slack_webhook_url, json={"text": "\n".join(lines)})
```

Config:
```python
slack_webhook_url: str = ""
api_base_url: str = "http://localhost:8000"
```

Three triggers in internal.py:
1. `decisions_emitted` (line 74) -- after storing decisions, before return
2. `phase_completed` (line 127) -- after advancing pipeline, before return
3. `phase_failed` (line 173) -- after exhausting retries, before return

## Changes
- [ ] src/pylon/notifications.py (NEW): `send_slack` helper, 3 notification formatters
- [ ] src/pylon/api/internal.py: Call notification functions at 3 trigger points

## Proposed implementation

```python
# src/pylon/notifications.py
import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)


async def send_slack(text: str) -> None:
    if not settings.slack_webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(settings.slack_webhook_url, json={"text": text})
    except Exception:
        logger.warning("Slack notification failed", exc_info=True)


async def notify_decisions_pending(slug: str, repo: str, assignee: str | None, phase: str, round_number: int, count: int):
    url = f"{settings.api_base_url}/tickets/{slug}/decisions"
    assignee_str = f" @{assignee}" if assignee else ""
    text = (
        f"*Pylon* -- {count} decisions pending\n"
        f"*{slug}* ({repo}){assignee_str}\n"
        f"{phase.title()} Round {round_number} -- <{url}|Answer decisions>"
    )
    await send_slack(text)


async def notify_phase_failed(slug: str, repo: str, phase: str, error: str):
    text = (
        f"*Pylon* -- phase failed\n"
        f"*{slug}* ({repo}) -- {phase} failed\n"
        f"```{error[:200]}```"
    )
    await send_slack(text)


async def notify_pipeline_completed(slug: str, repo: str, pr_url: str | None):
    pr_link = f" -- <{pr_url}|View PR>" if pr_url else ""
    text = f"*Pylon* -- pipeline complete\n*{slug}* ({repo}){pr_link}"
    await send_slack(text)
```

```python
# In internal.py decisions_emitted, after line 122 (await _sync_asana_status):
from ..notifications import notify_decisions_pending
await notify_decisions_pending(
    slug=pipeline.ticket.slug, repo=pipeline.ticket.repo,
    assignee=pipeline.ticket.assignee, phase=body.phase,
    round_number=body.round_number, count=len(body.decisions),
)

# In internal.py phase_completed, after line 168 (completed branch):
from ..notifications import notify_pipeline_completed
await notify_pipeline_completed(
    slug=pipeline.ticket.slug, repo=pipeline.ticket.repo, pr_url=pipeline.pr_url,
)

# In internal.py phase_failed, after line 219 (await _sync_asana_status, failed with no retries left):
from ..notifications import notify_phase_failed
await notify_phase_failed(
    slug=pipeline.ticket.slug, repo=pipeline.ticket.repo,
    phase=body.phase, error=body.error,
)
```

## Decisions
- [x] RESOLVED: Use mrkdwn formatting, not Block Kit (Decision 2, Option C)
- [x] RESOLVED: Fire-and-forget with logged warning on failure (matches existing pattern)

## Tests
Requirements: unit
Run: `pytest tests/test_notifications.py`
- [ ] send_slack skips when webhook_url empty
- [ ] notify_decisions_pending formats correct mrkdwn
- [ ] notify_phase_failed truncates long error messages

## Commit
```
feat(notifications): add Slack webhooks for decisions, failures, completions

Three Slack notification triggers using mrkdwn format. Fire-and-forget
with logged warnings on failure.

- Add notifications.py with send_slack helper and 3 formatters
- Call from internal API: decisions-emitted, phase-failed, pipeline-completed
- Skip silently when slack_webhook_url not configured
```

## Dependencies
blocked_by: none
blocks: none

## After commit
- Update status/PROGRESS.md: check 3 Slack notification items in "FastAPI backend" section
- Check off 3 items in status/backlog/critical-path.md under "Notifications"
