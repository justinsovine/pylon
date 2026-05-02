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


async def notify_decisions_pending(
    slug: str,
    repo: str,
    assignee: str | None,
    phase: str,
    round_number: int,
    count: int,
):
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
