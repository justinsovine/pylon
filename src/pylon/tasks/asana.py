import asyncio
import re

import httpx
from sqlalchemy import select

from ..config import settings
from ..database import async_session
from ..models import Pipeline, Ticket
from .celery_app import app


class AsanaClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://app.asana.com/api/1.0"
        self.headers = {"Authorization": f"Bearer {token}"}

    async def get_section_tasks(self, section_gid: str) -> list[dict]:
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/sections/{section_gid}/tasks",
                params={
                    "opt_fields": "gid,name,notes,assignee.name,custom_fields",
                    "limit": 20,
                },
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    async def update_task(self, task_gid: str, data: dict) -> dict:
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.put(
                f"{self.base_url}/tasks/{task_gid}",
                json={"data": data},
            )
            resp.raise_for_status()
            return resp.json().get("data", {})

    async def add_comment(self, task_gid: str, text: str) -> dict:
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/tasks/{task_gid}/stories",
                json={"data": {"text": text}},
            )
            resp.raise_for_status()
            return resp.json().get("data", {})

    async def set_enum_field(self, task_gid: str, field_gid: str, enum_value_gid: str) -> dict:
        return await self.update_task(
            task_gid,
            {"custom_fields": {field_gid: enum_value_gid}},
        )

    async def set_text_field(self, task_gid: str, field_gid: str, value: str) -> dict:
        return await self.update_task(
            task_gid,
            {"custom_fields": {field_gid: value}},
        )

    async def move_to_section(self, task_gid: str, section_gid: str) -> None:
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/sections/{section_gid}/addTask",
                json={"data": {"task": task_gid}},
            )
            resp.raise_for_status()


def slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug[:80].strip("-")


def _extract_custom_field(task: dict, field_name: str) -> str | None:
    for field in task.get("custom_fields") or []:
        if field.get("name", "").lower() == field_name.lower():
            if field.get("enum_value"):
                return field["enum_value"].get("name")
            if field.get("text_value"):
                return field["text_value"]
            if field.get("display_value"):
                return field["display_value"]
    return None


PYLON_STATUS_VALUES: dict[str, str] = {
    "investigate": "Investigating",
    "refine": "Refining",
    "plan": "Planning",
    "critique": "Critiquing",
    "implement": "Implementing",
    "test": "Testing",
    "pr": "Creating PR",
    "awaiting_decisions": "Awaiting Decisions",
    "completed": "Completed",
    "failed": "Failed",
}


async def sync_asana_fields(
    asana_gid: str,
    *,
    status: str | None = None,
    pr_url: str | None = None,
) -> None:
    if not settings.asana_token:
        return

    client = AsanaClient(settings.asana_token)

    if status and settings.asana_status_field_gid:
        display = PYLON_STATUS_VALUES.get(status, status)
        await client.set_text_field(
            asana_gid, settings.asana_status_field_gid, display
        )

    if pr_url and settings.asana_pr_field_gid:
        await client.set_text_field(
            asana_gid, settings.asana_pr_field_gid, pr_url
        )


@app.task
def poll_asana():
    if not settings.asana_token or not settings.asana_ready_section_gid:
        return {"skipped": "asana not configured"}

    return asyncio.run(_poll_asana())


async def _poll_asana():
    client = AsanaClient(settings.asana_token)
    tasks = await client.get_section_tasks(settings.asana_ready_section_gid)

    if not tasks:
        return {"polled": 0, "created": 0, "skipped": 0}

    asana_gids = [t["gid"] for t in tasks]

    async with async_session() as db:
        result = await db.execute(
            select(Ticket.asana_gid).where(Ticket.asana_gid.in_(asana_gids))
        )
        existing_gids = set(result.scalars().all())

        created = []
        for task in tasks:
            if task["gid"] in existing_gids:
                continue

            title = task.get("name", task["gid"])
            slug = slugify(title)

            repo = _extract_custom_field(task, "repo") or "onboard"
            priority = _extract_custom_field(task, "priority")
            assignee_name = None
            if task.get("assignee"):
                assignee_name = task["assignee"].get("name")

            ticket = Ticket(
                asana_gid=task["gid"],
                slug=slug,
                title=title,
                description=task.get("notes"),
                assignee=assignee_name,
                repo=repo,
                priority=priority,
            )
            db.add(ticket)
            await db.flush()

            pipeline = Pipeline(
                ticket_id=ticket.id,
                status="queued",
                notes_path=f"notes/{slug}",
                branch_name=f"pylon/{slug}",
            )
            db.add(pipeline)
            await db.flush()

            created.append(str(pipeline.id))

        await db.commit()

    from .pipeline import run_phase

    for pipeline_id in created:
        run_phase.delay(pipeline_id, "investigate")

    return {
        "polled": len(tasks),
        "created": len(created),
        "skipped": len(existing_gids),
    }
