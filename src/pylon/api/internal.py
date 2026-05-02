import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..database import get_db
from ..models import Decision, DecisionRound, PhaseRun, Pipeline
from ..schemas import DecisionsEmitted, PhaseCompleted, PhaseFailed, PhaseStarted, ProgressUpdate
from ..tasks.asana import sync_asana_fields
from ..tasks.pipeline import run_phase

logger = logging.getLogger(__name__)


async def _sync_asana_status(pipeline: Pipeline, status: str, pr_url: str | None = None):
    if not pipeline.ticket or not pipeline.ticket.asana_gid:
        return
    try:
        await sync_asana_fields(
            pipeline.ticket.asana_gid,
            status=status,
            pr_url=pr_url,
        )
    except Exception:
        logger.warning("Asana sync failed for pipeline %s", pipeline.id, exc_info=True)

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
    query = (
        select(Pipeline)
        .options(selectinload(Pipeline.ticket))
        .where(Pipeline.id == body.pipeline_id)
    )
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

    await _sync_asana_status(pipeline, body.phase)

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

    query = (
        select(Pipeline)
        .options(selectinload(Pipeline.ticket))
        .where(Pipeline.id == body.pipeline_id)
    )
    result = await db.execute(query)
    pipeline = result.scalar_one()
    pipeline.status = "awaiting_decisions"

    await db.commit()

    await _sync_asana_status(pipeline, "awaiting_decisions")

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

    query = (
        select(Pipeline)
        .options(selectinload(Pipeline.ticket))
        .where(Pipeline.id == body.pipeline_id)
    )
    result = await db.execute(query)
    pipeline = result.scalar_one()

    pr_url = body.result.get("pr_url")
    if pr_url:
        pipeline.pr_url = pr_url

    current_idx = PHASE_ORDER.index(body.phase) if body.phase in PHASE_ORDER else -1
    if current_idx < len(PHASE_ORDER) - 1:
        next_phase = PHASE_ORDER[current_idx + 1]
        pipeline.current_phase = next_phase
        pipeline.status = next_phase
        await db.commit()
        await _sync_asana_status(pipeline, next_phase)
        run_phase.delay(str(pipeline.id), next_phase)
    else:
        pipeline.status = "completed"
        pipeline.completed_at = datetime.utcnow()
        await db.commit()
        await _sync_asana_status(pipeline, "completed", pr_url=pipeline.pr_url)

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

    await db.flush()

    query = (
        select(Pipeline)
        .options(selectinload(Pipeline.ticket))
        .where(Pipeline.id == body.pipeline_id)
    )
    result = await db.execute(query)
    pipeline = result.scalar_one()

    if body.retry_safe:
        failed_count = (await db.execute(
            select(func.count())
            .select_from(PhaseRun)
            .where(PhaseRun.pipeline_id == body.pipeline_id)
            .where(PhaseRun.phase == body.phase)
            .where(PhaseRun.status == "failed")
        )).scalar()

        if failed_count <= settings.max_phase_retries:
            pipeline.status = body.phase
            await db.commit()
            run_phase.delay(str(body.pipeline_id), body.phase)
            return {"retry_safe": True, "action": "retrying", "attempt": failed_count + 1}

    pipeline.status = "failed"
    await db.commit()

    await _sync_asana_status(pipeline, "failed")

    return {"retry_safe": body.retry_safe}


@router.post("/progress", dependencies=[Depends(verify_internal_key)])
async def progress_update(body: ProgressUpdate):
    # TODO: store in Redis for fast dashboard polling (not worth a DB write)
    return {"ok": True}
