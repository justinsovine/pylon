from pathlib import Path

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .api import decisions, internal, pipelines, workers
from .database import get_db
from .models import Decision, DecisionRound, PhaseRun, Pipeline, Ticket
from .redis import get_progress

app = FastAPI(title="Pylon", version="0.1.0")

templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(templates_dir))
templates.env.cache = None
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/api/progress/{pipeline_id}")
async def get_pipeline_progress(pipeline_id: str):
    data = await get_progress(pipeline_id)
    return data or {"phase": None, "progress": 0, "message": ""}


app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(decisions.router, prefix="/api/decisions", tags=["decisions"])
app.include_router(workers.router, prefix="/api/workers", tags=["workers"])
app.include_router(internal.router, prefix="/api/internal", tags=["internal"])


@app.get("/", response_class=HTMLResponse)
async def board(request: Request):
    return templates.TemplateResponse(request, "board.html")


@app.get("/tickets/{slug}", response_class=HTMLResponse)
async def ticket_detail(request: Request, slug: str):
    return templates.TemplateResponse(request, "ticket.html", {"slug": slug})


@app.get("/tickets/{slug}/decisions", response_class=HTMLResponse)
async def ticket_decisions(request: Request, slug: str):
    return templates.TemplateResponse(request, "decisions.html", {"slug": slug})


@app.get("/activity", response_class=HTMLResponse)
async def activity(request: Request):
    return templates.TemplateResponse(request, "activity.html")


@app.get("/partials/activity", response_class=HTMLResponse)
async def activity_partial(request: Request, db: AsyncSession = Depends(get_db)):
    recent_runs = (
        await db.execute(
            select(PhaseRun)
            .join(Pipeline)
            .join(Ticket)
            .options(selectinload(PhaseRun.pipeline).selectinload(Pipeline.ticket))
            .order_by(PhaseRun.created_at.desc())
            .limit(50)
        )
    ).scalars().all()

    events = []
    for run in recent_runs:
        slug = run.pipeline.ticket.slug
        assignee = run.pipeline.ticket.assignee
        pid = run.pipeline_id
        if run.started_at:
            events.append({
                "ts": run.started_at, "type": "started", "slug": slug,
                "assignee": assignee, "msg": f"{run.phase} started", "pid": pid,
            })
        if run.completed_at and run.status == "completed":
            events.append({
                "ts": run.completed_at, "type": "completed", "slug": slug,
                "assignee": assignee, "msg": f"{run.phase} completed", "pid": pid,
            })
        if run.completed_at and run.status == "failed":
            err = run.error_message or "unknown"
            events.append({
                "ts": run.completed_at, "type": "failed", "slug": slug,
                "assignee": assignee, "msg": f"{run.phase} failed: {err}", "pid": pid,
            })

    events.sort(key=lambda e: e["ts"], reverse=True)
    return templates.TemplateResponse(
        request, "partials/activity.html", {"events": events[:50]},
    )


PHASE_ORDER = ["investigate", "refine", "plan", "critique", "implement", "test", "pr"]


@app.get("/partials/badge", response_class=HTMLResponse)
async def badge_partial(request: Request, db: AsyncSession = Depends(get_db)):
    count = (
        await db.execute(
            select(func.count()).select_from(DecisionRound).where(DecisionRound.status == "awaiting")
        )
    ).scalar()
    return templates.TemplateResponse(request, "partials/badge.html", {"count": count})


@app.get("/partials/ticket/{slug}", response_class=HTMLResponse)
async def ticket_partial(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    ticket = (
        await db.execute(select(Ticket).where(Ticket.slug == slug))
    ).scalar_one_or_none()
    if not ticket:
        return HTMLResponse("<p class='text-red-400'>Ticket not found.</p>")

    pipeline = (
        await db.execute(
            select(Pipeline)
            .where(Pipeline.ticket_id == ticket.id)
            .options(selectinload(Pipeline.phase_runs))
        )
    ).scalar_one_or_none()

    return templates.TemplateResponse(
        request,
        "partials/ticket.html",
        {"ticket": ticket, "pipeline": pipeline, "phases": PHASE_ORDER},
    )


@app.get("/partials/decisions/{slug}", response_class=HTMLResponse)
async def decisions_partial(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    ticket = (
        await db.execute(select(Ticket).where(Ticket.slug == slug))
    ).scalar_one_or_none()
    if not ticket:
        return HTMLResponse("<p class='text-gray-500'>No ticket found.</p>")

    pipeline = (
        await db.execute(
            select(Pipeline)
            .where(Pipeline.ticket_id == ticket.id)
            .options(
                selectinload(Pipeline.phase_runs)
                .selectinload(PhaseRun.decision_rounds)
                .selectinload(DecisionRound.decisions)
                .selectinload(Decision.answer)
            )
        )
    ).scalar_one_or_none()
    if not pipeline:
        return HTMLResponse("<p class='text-gray-500'>No pipeline found.</p>")

    awaiting_round = None
    phase = None
    for pr in pipeline.phase_runs:
        for dr in pr.decision_rounds:
            if dr.status == "awaiting":
                awaiting_round = dr
                phase = pr.phase
                break
        if awaiting_round:
            break

    return templates.TemplateResponse(
        request,
        "partials/decisions.html",
        {
            "pipeline": pipeline,
            "round": awaiting_round,
            "phase": phase,
        },
    )


BOARD_COLUMNS = [
    ("Queued", lambda p: p.status == "queued"),
    (
        "Investigating",
        lambda p: p.current_phase in ("investigate", "refine") and p.status != "awaiting_decisions",
    ),
    ("Decisions", lambda p: p.status == "awaiting_decisions"),
    (
        "Planning",
        lambda p: p.current_phase in ("plan", "critique") and p.status != "awaiting_decisions",
    ),
    (
        "Implementing",
        lambda p: p.current_phase in ("implement", "test") and p.status != "awaiting_decisions",
    ),
    (
        "PR Ready",
        lambda p: p.current_phase == "pr" or (p.status == "completed" and p.pr_url),
    ),
]


@app.get("/partials/board", response_class=HTMLResponse)
async def board_partial(
    request: Request,
    assignee: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Pipeline)
        .join(Ticket)
        .options(selectinload(Pipeline.ticket))
        .where(Pipeline.status.notin_(["cancelled"]))
        .order_by(Pipeline.updated_at.desc())
    )
    if assignee:
        query = query.where(Ticket.assignee == assignee)

    result = await db.execute(query)
    pipelines_list = result.scalars().all()

    columns = []
    for name, pred in BOARD_COLUMNS:
        columns.append({"name": name, "pipelines": [p for p in pipelines_list if pred(p)]})

    return templates.TemplateResponse(
        request,
        "partials/board.html",
        {"columns": columns},
    )
