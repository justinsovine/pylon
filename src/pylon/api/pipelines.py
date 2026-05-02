import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import Pipeline, Ticket
from ..schemas import PipelineCreate, PipelineOut
from ..tasks.pipeline import run_phase

router = APIRouter()


@router.get("", response_model=list[PipelineOut])
async def list_pipelines(
    assignee: str | None = None,
    status: str | None = None,
    repo: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Pipeline).join(Ticket).options(selectinload(Pipeline.ticket))

    if assignee:
        query = query.where(Ticket.assignee == assignee)
    if status:
        query = query.where(Pipeline.status == status)
    if repo:
        query = query.where(Ticket.repo == repo)

    query = query.order_by(Pipeline.updated_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{pipeline_id}", response_model=PipelineOut)
async def get_pipeline(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Pipeline)
        .where(Pipeline.id == pipeline_id)
        .options(selectinload(Pipeline.ticket))
    )
    result = await db.execute(query)
    pipeline = result.scalar_one()
    return pipeline


@router.post("", response_model=PipelineOut)
async def create_pipeline(
    body: PipelineCreate,
    db: AsyncSession = Depends(get_db),
):
    slug = body.asana_gid  # TODO: fetch title from Asana, slugify
    ticket = Ticket(
        asana_gid=body.asana_gid,
        slug=slug,
        title=slug,
        repo=body.repo,
        assignee=body.assignee,
    )
    db.add(ticket)
    await db.flush()

    pipeline = Pipeline(
        ticket_id=ticket.id,
        status="queued",
        notes_path=f"notes/{slug}",
        branch_name=f"feature/{slug}",
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)

    run_phase.delay(str(pipeline.id), "investigate")

    return pipeline


@router.post("/{pipeline_id}/cancel")
async def cancel_pipeline(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    query = select(Pipeline).where(Pipeline.id == pipeline_id)
    result = await db.execute(query)
    pipeline = result.scalar_one()
    pipeline.status = "cancelled"
    pipeline.completed_at = datetime.utcnow()
    await db.commit()
    return {"status": "cancelled"}


@router.post("/{pipeline_id}/retry")
async def retry_pipeline(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    query = select(Pipeline).where(Pipeline.id == pipeline_id)
    result = await db.execute(query)
    pipeline = result.scalar_one()

    if pipeline.status != "failed":
        return {"error": "can only retry failed pipelines"}

    pipeline.status = pipeline.current_phase or "queued"
    await db.commit()

    run_phase.delay(str(pipeline.id), pipeline.current_phase or "investigate")

    return {"status": "retrying", "phase": pipeline.current_phase}
