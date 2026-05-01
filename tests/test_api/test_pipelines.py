import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_pipeline, make_ticket


@pytest.mark.asyncio
async def test_list_pipelines_empty(client: AsyncClient):
    resp = await client.get("/api/pipelines")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_pipeline(client: AsyncClient):
    resp = await client.post("/api/pipelines", json={
        "asana_gid": "12345",
        "repo": "onboard",
        "assignee": "justin",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["ticket"]["repo"] == "onboard"


@pytest.mark.asyncio
async def test_list_pipelines_filtered(client: AsyncClient, db: AsyncSession):
    ticket = make_ticket(assignee="tanya", repo="scriptus-web")
    db.add(ticket)
    pipeline = make_pipeline(ticket, status="investigating")
    db.add(pipeline)
    await db.commit()

    resp = await client.get("/api/pipelines", params={"assignee": "tanya"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "investigating"
