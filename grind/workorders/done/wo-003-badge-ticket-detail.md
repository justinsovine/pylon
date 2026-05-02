# WO-003: Badge + ticket detail partials

## Scope
Pending decision count badge in nav, ticket detail with phase timeline. Small.

## Files to read
- src/pylon/templates/base.html (line 22: badge HTMX target)
- src/pylon/templates/ticket.html (full file, small: HTMX shell)
- src/pylon/main.py (add two partial routes)
- src/pylon/models.py (lines 57-74: PhaseRun, lines 77-91: DecisionRound)
- src/pylon/api/internal.py (line 33: PHASE_ORDER)

## Key context

Badge target in nav (base.html line 22):
```html
<span hx-get="/partials/badge" hx-trigger="every 30s" hx-swap="innerHTML"
      class="text-sm text-amber-400" id="badge">
</span>
```

Ticket detail shell (ticket.html line 6):
```html
<div id="ticket-detail" hx-get="/partials/ticket/{{ slug }}" hx-trigger="load, every 10s" hx-swap="innerHTML">
```

PhaseRun model:
```python
class PhaseRun(Base):
    phase: Mapped[str]
    status: Mapped[str]  # pending, running, awaiting_decisions, completed, failed
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    error_message: Mapped[str | None]
```

PHASE_ORDER = ["investigate", "refine", "plan", "critique", "implement", "test", "pr"]

## Changes
- [ ] src/pylon/main.py: Add `/partials/badge` and `/partials/ticket/{slug}` routes
- [ ] src/pylon/templates/partials/badge.html (NEW): Pending count or empty
- [ ] src/pylon/templates/partials/ticket.html (NEW): Phase timeline, ticket info, links

## Proposed implementation

```python
# Badge route:
@app.get("/partials/badge", response_class=HTMLResponse)
async def badge_partial(request: Request, db: AsyncSession = Depends(get_db)):
    count = (await db.execute(
        select(func.count()).select_from(DecisionRound).where(DecisionRound.status == "awaiting")
    )).scalar()
    return templates.TemplateResponse("partials/badge.html", {"request": request, "count": count})

# Ticket detail route:
@app.get("/partials/ticket/{slug}", response_class=HTMLResponse)
async def ticket_partial(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    ticket = (await db.execute(
        select(Ticket).where(Ticket.slug == slug)
    )).scalar_one_or_none()
    if not ticket:
        return HTMLResponse("<p class='text-red-400'>Ticket not found.</p>")

    pipeline = (await db.execute(
        select(Pipeline)
        .where(Pipeline.ticket_id == ticket.id)
        .options(selectinload(Pipeline.phase_runs))
    )).scalar_one_or_none()

    phases = PHASE_ORDER  # for timeline display
    return templates.TemplateResponse("partials/ticket.html", {
        "request": request, "ticket": ticket, "pipeline": pipeline, "phases": phases,
    })
```

Badge template:
```html
{% if count > 0 %}{{ count }} pending{% endif %}
```

Ticket detail template: phase timeline (7 dots), ticket metadata, links to decisions/PR.

## Decisions
- [x] RESOLVED: Badge shows count only when > 0 (no "0 pending" clutter)

## Tests
Requirements: manual
- [ ] Badge shows count when decisions awaiting
- [ ] Badge empty when nothing pending
- [ ] Ticket detail shows phase timeline with completed/current/upcoming states
- [ ] Links to decisions page and PR work

## Commit
```
feat(dashboard): add badge and ticket detail partials

Badge shows pending decision count in nav, polls every 30s. Ticket
detail shows phase timeline, metadata, and action links.

- Register /partials/badge and /partials/ticket/{slug} routes
- Badge partial shows count only when decisions are awaiting
- Ticket partial renders 7-phase timeline with status indicators
```

## Dependencies
blocked_by: none (wo-001 completed 2026-05-02)
blocks: none

## After commit
- Update status/PROGRESS.md: check "Badge partial showing pending decision count" and "Ticket detail partial with phase progress and history"
