from pathlib import Path

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .api import decisions, internal, pipelines, workers
from .database import get_db
from .models import Pipeline, Ticket

app = FastAPI(title="Pylon", version="0.1.0")

templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(templates_dir))
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(decisions.router, prefix="/api/decisions", tags=["decisions"])
app.include_router(workers.router, prefix="/api/workers", tags=["workers"])
app.include_router(internal.router, prefix="/api/internal", tags=["internal"])


@app.get("/", response_class=HTMLResponse)
async def board(request: Request):
    return templates.TemplateResponse("board.html", {"request": request})


@app.get("/tickets/{slug}", response_class=HTMLResponse)
async def ticket_detail(request: Request, slug: str):
    return templates.TemplateResponse("ticket.html", {"request": request, "slug": slug})


@app.get("/tickets/{slug}/decisions", response_class=HTMLResponse)
async def ticket_decisions(request: Request, slug: str):
    return templates.TemplateResponse("decisions.html", {"request": request, "slug": slug})


@app.get("/activity", response_class=HTMLResponse)
async def activity(request: Request):
    return templates.TemplateResponse("activity.html", {"request": request})


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
        "partials/board.html",
        {
            "request": request,
            "columns": columns,
        },
    )
