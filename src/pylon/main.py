from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api import decisions, internal, pipelines, workers

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
