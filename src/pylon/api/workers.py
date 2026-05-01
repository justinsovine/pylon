import uuid

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import WorkerSession
from ..schemas import WorkerSessionOut

router = APIRouter()


@router.get("", response_model=list[WorkerSessionOut])
async def list_workers(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(WorkerSession)
    if status:
        query = query.where(WorkerSession.status == status)
    query = query.order_by(WorkerSession.started_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{worker_id}", response_model=WorkerSessionOut)
async def get_worker(
    worker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    query = select(WorkerSession).where(WorkerSession.id == worker_id)
    result = await db.execute(query)
    return result.scalar_one()


@router.post("/{worker_id}/kill")
async def kill_worker(
    worker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    query = select(WorkerSession).where(WorkerSession.id == worker_id)
    result = await db.execute(query)
    worker = result.scalar_one()

    if worker.pid and psutil.pid_exists(worker.pid):
        proc = psutil.Process(worker.pid)
        proc.terminate()
        worker.status = "killed"
    else:
        worker.status = "failed"
        worker.error_output = "Process not found"

    await db.commit()
    return {"status": worker.status}
