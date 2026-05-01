import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    make_decision,
    make_decision_round,
    make_phase_run,
    make_pipeline,
    make_ticket,
)


@pytest.mark.asyncio
async def test_list_pending_decisions_empty(client: AsyncClient):
    resp = await client.get("/api/decisions/pending")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_submit_answers(client: AsyncClient, db: AsyncSession):
    ticket = make_ticket()
    db.add(ticket)
    pipeline = make_pipeline(ticket, status="awaiting_decisions")
    db.add(pipeline)
    phase_run = make_phase_run(pipeline, phase="refine", status="awaiting_decisions")
    db.add(phase_run)
    round_ = make_decision_round(phase_run)
    db.add(round_)
    decision = make_decision(round_, decision_key="d001")
    db.add(decision)
    await db.commit()

    resp = await client.post(f"/api/decisions/rounds/{round_.id}/answers", json={
        "answers": [
            {"decision_id": str(decision.id), "choice": "A", "note": "go simple"},
        ],
        "answered_by": "justin",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["round_status"] == "answered"
