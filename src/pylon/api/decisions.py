import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import Answer, Decision, DecisionRound, PhaseRun, Pipeline, Ticket
from ..schemas import AnswerBatchSubmit, DecisionOut, DecisionRoundOut

router = APIRouter()


@router.get("/pending", response_model=list[DecisionOut])
async def list_pending_decisions(
    assignee: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Decision)
        .join(DecisionRound)
        .join(PhaseRun)
        .join(Pipeline)
        .join(Ticket)
        .outerjoin(Answer)
        .where(DecisionRound.status == "awaiting")
        .where(Answer.id.is_(None))
        .options(selectinload(Decision.answer))
    )

    if assignee:
        query = query.where(Ticket.assignee == assignee)

    query = query.order_by(DecisionRound.emitted_at)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/rounds/{round_id}", response_model=DecisionRoundOut)
async def get_round(
    round_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(DecisionRound)
        .where(DecisionRound.id == round_id)
        .options(selectinload(DecisionRound.decisions).selectinload(Decision.answer))
    )
    result = await db.execute(query)
    return result.scalar_one()


@router.post("/rounds/{round_id}/answers")
async def submit_answers(
    round_id: uuid.UUID,
    body: AnswerBatchSubmit,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(DecisionRound)
        .where(DecisionRound.id == round_id)
        .options(selectinload(DecisionRound.decisions))
    )
    result = await db.execute(query)
    round_ = result.scalar_one()

    for answer_data in body.answers:
        answer = Answer(
            decision_id=answer_data.decision_id,
            choice=answer_data.choice,
            note=answer_data.note,
            answered_by=body.answered_by,
            source="dashboard",
        )
        db.add(answer)

    all_answered = len(body.answers) >= len(round_.decisions)
    if all_answered:
        round_.status = "answered"
        round_.answered_at = datetime.utcnow()

    await db.commit()

    # TODO: if all answered, write answers file and trigger next worker invocation

    return {
        "round_status": round_.status,
        "next_action": "resuming_phase" if all_answered else "partial_answers_saved",
    }
