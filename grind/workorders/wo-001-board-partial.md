# WO-001: Dashboard partial routes + board kanban

## Scope
Register all `/partials/*` routes in main.py, implement board partial with pipeline cards in 6 kanban columns. Medium.

## Files to read
- src/pylon/main.py (full file, small: add partial routes)
- src/pylon/templates/board.html (full file, small: HTMX shell already wired)
- src/pylon/templates/base.html (full file, small: nav references /partials/badge)
- src/pylon/models.py (lines 35-54: Pipeline model, status field, ticket relationship)
- src/pylon/database.py (full file, small: get_db dependency)
- src/pylon/api/pipelines.py (lines 17-35: list_pipelines query pattern)

## Key context

Existing page routes in main.py (lines 24-41):
```python
@app.get("/", response_class=HTMLResponse)
async def board(request: Request):
    return templates.TemplateResponse("board.html", {"request": request})

@app.get("/tickets/{slug}", response_class=HTMLResponse)
async def ticket_detail(request: Request, slug: str):
    return templates.TemplateResponse("ticket.html", {"request": request, "slug": slug})
```

HTMX board shell (board.html line 4):
```html
<div class="flex gap-4 overflow-x-auto" hx-get="/partials/board" hx-trigger="every 10s" hx-swap="innerHTML">
```

Pipeline query pattern (pipelines.py lines 24-35):
```python
query = select(Pipeline).join(Ticket).options(selectinload(Pipeline.ticket))
if assignee:
    query = query.where(Ticket.assignee == assignee)
query = query.order_by(Pipeline.updated_at.desc())
result = await db.execute(query)
return result.scalars().all()
```

Column mapping (Decision 1 resolved):
- Queued = status `queued`
- Investigating = phase `investigate`
- Decisions = status `awaiting_decisions`
- Planning = phase in (`plan`, `critique`)
- Implementing = phase in (`implement`, `test`)
- PR Ready = phase `pr` or status `completed` with pr_url

Pipeline statuses stored as: `queued`, `investigate`, `refine`, `plan`, `critique`, `implement`, `test`, `completed`, `failed`, `cancelled`, `awaiting_decisions`

Phase order constant (internal.py line 33):
```python
PHASE_ORDER = ["investigate", "refine", "plan", "critique", "implement", "test", "pr"]
```

## Changes
- [ ] src/pylon/main.py (lines 22+): Add `/partials/board` route with DB query and column grouping
- [ ] src/pylon/templates/partials/ (NEW dir): Create partials directory
- [ ] src/pylon/templates/partials/board.html (NEW): Kanban columns with pipeline cards

## Proposed implementation

```python
# In main.py, add after existing routes:

from .database import get_db
from .models import Pipeline, Ticket
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Query

BOARD_COLUMNS = [
    ("Queued", lambda p: p.status == "queued"),
    ("Investigating", lambda p: p.current_phase in ("investigate", "refine") and p.status != "awaiting_decisions"),
    ("Decisions", lambda p: p.status == "awaiting_decisions"),
    ("Planning", lambda p: p.current_phase in ("plan", "critique") and p.status != "awaiting_decisions"),
    ("Implementing", lambda p: p.current_phase in ("implement", "test") and p.status != "awaiting_decisions"),
    ("PR Ready", lambda p: p.current_phase == "pr" or (p.status == "completed" and p.pr_url)),
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
    pipelines = result.scalars().all()

    columns = []
    for name, pred in BOARD_COLUMNS:
        columns.append({"name": name, "pipelines": [p for p in pipelines if pred(p)]})

    return templates.TemplateResponse("partials/board.html", {
        "request": request,
        "columns": columns,
    })
```

Board partial template (Tailwind dark theme, matches base.html):
```html
<!-- partials/board.html -->
{% for col in columns %}
<div class="flex-shrink-0 w-64 bg-gray-900 rounded-lg p-3">
    <h3 class="text-sm font-medium text-gray-400 mb-3">{{ col.name }} ({{ col.pipelines|length }})</h3>
    {% for p in col.pipelines %}
    <a href="/tickets/{{ p.ticket.slug }}"
       class="block bg-gray-800 rounded p-3 mb-2 hover:bg-gray-750 border border-gray-700
              {% if p.status == 'failed' %}border-red-500{% endif %}">
        <div class="font-medium text-sm text-white">{{ p.ticket.slug }}</div>
        <div class="flex items-center gap-2 mt-1">
            <span class="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-300">{{ p.ticket.repo }}</span>
            {% if p.ticket.assignee %}
            <span class="text-xs text-gray-500">@{{ p.ticket.assignee }}</span>
            {% endif %}
        </div>
        {% if p.status == 'awaiting_decisions' %}
        <a href="/tickets/{{ p.ticket.slug }}/decisions"
           class="mt-2 inline-block text-xs text-amber-400 hover:text-amber-300">Answer decisions</a>
        {% elif p.pr_url %}
        <a href="{{ p.pr_url }}" target="_blank"
           class="mt-2 inline-block text-xs text-blue-400 hover:text-blue-300">View PR</a>
        {% elif p.current_phase %}
        <div class="mt-1 text-xs text-gray-500">{{ p.current_phase }}</div>
        {% endif %}
    </a>
    {% endfor %}
    {% if not col.pipelines %}
    <p class="text-xs text-gray-600 italic">Empty</p>
    {% endif %}
</div>
{% endfor %}
```

## Decisions
- [x] RESOLVED: Column mapping -- 6 columns matching BUILDPLAN (Decision 1, Option A)
- [x] RESOLVED: No auth -- assignee filter via query param dropdown (Decision 3, Option B)

## Tests
Requirements: manual
Run: `just dev` then open http://localhost:8000
- [ ] Board loads with 6 empty columns
- [ ] Seed data pipeline card appears in correct column
- [ ] Clicking card navigates to ticket detail
- [ ] 10s HTMX refresh works without flicker
- [ ] Assignee filter query param works (?assignee=justin)

## Commit
```
feat(dashboard): add board partial with kanban columns

Board partial renders pipeline cards in 6 columns (Queued, Investigating,
Decisions, Planning, Implementing, PR Ready). HTMX polls every 10s.

- Register /partials/board route in main.py with DB query
- Create partials/board.html template with Tailwind dark theme
- Group pipelines by status/phase into column buckets
- Show repo badge, assignee, and phase-specific actions on cards
```

## Dependencies
blocked_by: none
blocks: wo-002, wo-003, wo-004

## After commit
- Update status/PROGRESS.md: "HTMX frontend" section, check "Board partial rendering pipeline cards in columns"
