from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models import Decision, DecisionRound, PhaseRun, Pipeline
from ..schemas import DecisionsEmitted, PhaseCompleted, PhaseFailed, PhaseStarted, ProgressUpdate

router = APIRouter()

PHASE_ORDER = ["investigate", "refine", "plan", "critique", "implement", "test", "pr"]


def verify_internal_key(x_pylon_key: str = Header()):
    if x_pylon_key != settings.pylon_internal_key:
        raise HTTPException(status_code=401, detail="invalid internal key")


@router.post("/phase-started", dependencies=[Depends(verify_internal_key)])
async def phase_started(
    body: PhaseStarted,
    db: AsyncSession = Depends(get_db),
):
    query = select(Pipeline).where(Pipeline.id == body.pipeline_id)
    result = await db.execute(query)
    pipeline = result.scalar_one()

    pipeline.status = body.phase
    pipeline.current_phase = body.phase
    if not pipeline.started_at:
        pipeline.started_at = datetime.utcnow()

    phase_run = PhaseRun(
        pipeline_id=pipeline.id,
        phase=body.phase,
        status="running",
        started_at=datetime.utcnow(),
        worker_id=body.worker_id,
    )
    db.add(phase_run)
    await db.commit()
    return {"phase_run_id": str(phase_run.id)}


@router.post("/decisions-emitted", dependencies=[Depends(verify_internal_key)])
async def decisions_emitted(
    body: DecisionsEmitted,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(PhaseRun)
        .where(PhaseRun.pipeline_id == body.pipeline_id)
        .where(PhaseRun.phase == body.phase)
        .where(PhaseRun.status == "running")
    )
    result = await db.execute(query)
    phase_run = result.scalar_one()
    phase_run.status = "awaiting_decisions"

    round_ = DecisionRound(
        phase_run_id=phase_run.id,
        round_number=body.round_number,
        status="awaiting",
        emitted_at=datetime.utcnow(),
    )
    db.add(round_)
    await db.flush()

    for d in body.decisions:
        decision = Decision(
            round_id=round_.id,
            decision_key=d["id"],
            question=d["question"],
            context=d.get("context"),
            options=d.get("options", []),
            recommendation=d.get("recommendation"),
            recommendation_why=d.get("recommendation_why"),
            depends_on=d.get("depends_on"),
        )
        db.add(decision)

    query = select(Pipeline).where(Pipeline.id == body.pipeline_id)
    result = await db.execute(query)
    pipeline = result.scalar_one()
    pipeline.status = "awaiting_decisions"

    await db.commit()

    # TODO: send notification to assigned dev

    return {"round_id": str(round_.id), "decisions_count": len(body.decisions)}


@router.post("/phase-completed", dependencies=[Depends(verify_internal_key)])
async def phase_completed(
    body: PhaseCompleted,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(PhaseRun)
        .where(PhaseRun.pipeline_id == body.pipeline_id)
        .where(PhaseRun.phase == body.phase)
        .order_by(PhaseRun.created_at.desc())
    )
    result = await db.execute(query)
    phase_run = result.scalars().first()
    if phase_run:
        phase_run.status = "completed"
        phase_run.completed_at = datetime.utcnow()

    query = select(Pipeline).where(Pipeline.id == body.pipeline_id)
    result = await db.execute(query)
    pipeline = result.scalar_one()

    if body.result.get("pr_url"):
        pipeline.pr_url = body.result["pr_url"]

    current_idx = PHASE_ORDER.index(body.phase) if body.phase in PHASE_ORDER else -1
    if current_idx < len(PHASE_ORDER) - 1:
        next_phase = PHASE_ORDER[current_idx + 1]
        pipeline.current_phase = next_phase
        pipeline.status = next_phase
        # TODO: auto-dispatch next phase if non-decision phase
    else:
        pipeline.status = "completed"
        pipeline.completed_at = datetime.utcnow()

    await db.commit()
    return {"next_phase": pipeline.current_phase, "pipeline_status": pipeline.status}


@router.post("/phase-failed", dependencies=[Depends(verify_internal_key)])
async def phase_failed(
    body: PhaseFailed,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(PhaseRun)
        .where(PhaseRun.pipeline_id == body.pipeline_id)
        .where(PhaseRun.phase == body.phase)
        .order_by(PhaseRun.created_at.desc())
    )
    result = await db.execute(query)
    phase_run = result.scalars().first()
    if phase_run:
        phase_run.status = "failed"
        phase_run.error_message = body.error
        phase_run.completed_at = datetime.utcnow()

    query = select(Pipeline).where(Pipeline.id == body.pipeline_id)
    result = await db.execute(query)
    pipeline = result.scalar_one()
    pipeline.status = "failed"

    await db.commit()

    # TODO: auto-retry if retry_safe and retries remaining
    # TODO: notify assigned dev

    return {"retry_safe": body.retry_safe}


@router.post("/progress", dependencies=[Depends(verify_internal_key)])
async def progress_update(body: ProgressUpdate):
    # TODO: store in Redis for fast dashboard polling (not worth a DB write)
    return {"ok": True}
