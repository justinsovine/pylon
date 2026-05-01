"""Check emails sent by the app via Mailpit API.

Each Laravel app has a Mailpit container accessible on the edoc network.
"""

import httpx

MAILPIT_HOSTS = {
    "esign": "http://esign-mailpit:8025",
    "onboard": "http://onboard-mailpit:8025",
    "scriptus-web": "http://scriptus-mailpit:8025",
}


async def get_recent_messages(repo: str, limit: int = 10) -> list[dict]:
    host = MAILPIT_HOSTS.get(repo)
    if not host:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{host}/api/v1/messages", params={"limit": limit})
            resp.raise_for_status()
            data = resp.json()
            return data.get("messages", [])
    except (httpx.HTTPError, Exception):
        return []


async def search_messages(repo: str, query: str) -> list[dict]:
    host = MAILPIT_HOSTS.get(repo)
    if not host:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{host}/api/v1/search", params={"query": query})
            resp.raise_for_status()
            data = resp.json()
            return data.get("messages", [])
    except (httpx.HTTPError, Exception):
        return []


async def get_message(repo: str, message_id: str) -> dict:
    host = MAILPIT_HOSTS.get(repo)
    if not host:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{host}/api/v1/message/{message_id}")
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, Exception):
        return {}


async def delete_all_messages(repo: str) -> bool:
    host = MAILPIT_HOSTS.get(repo)
    if not host:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(f"{host}/api/v1/messages")
            return resp.status_code == 200
    except (httpx.HTTPError, Exception):
        return False
