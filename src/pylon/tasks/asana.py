import httpx

from ..config import settings
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

    async def move_to_section(self, task_gid: str, section_gid: str) -> None:
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/sections/{section_gid}/addTask",
                json={"data": {"task": task_gid}},
            )
            resp.raise_for_status()


@app.task
def poll_asana():
    if not settings.asana_token or not settings.asana_ready_section_gid:
        return {"skipped": "asana not configured"}

    import asyncio

    return asyncio.run(_poll_asana())


async def _poll_asana():
    client = AsanaClient(settings.asana_token)
    tasks = await client.get_section_tasks(settings.asana_ready_section_gid)

    created = []
    for task in tasks:
        # TODO: check if ticket already exists in DB
        # TODO: create ticket + pipeline
        # TODO: dispatch investigate phase
        created.append(task["gid"])

    return {"polled": len(tasks), "created": len(created)}
