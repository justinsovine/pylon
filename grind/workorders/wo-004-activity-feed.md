# WO-004: Activity feed partial

## Scope
Activity feed showing recent phase transitions, decisions answered, errors. Small.

## Files to read
- src/pylon/templates/activity.html (full file, small: HTMX shell)
- src/pylon/main.py (add partial route)
- src/pylon/models.py (lines 57-74: PhaseRun with timestamps)
- src/pylon/schemas.py (lines 144-151: ActivityEntry schema)

## Key context

Activity shell (activity.html line 6):
```html
<div id="activity-feed" hx-get="/partials/activity" hx-trigger="load, every 30s" hx-swap="innerHTML">
```

ActivityEntry schema already defined:
```python
class ActivityEntry(BaseModel):
    timestamp: datetime
    event_type: str
    pipeline_id: uuid.UUID
    ticket_slug: str
    assignee: str | None
    message: str
```

PhaseRun has `started_at`, `completed_at`, `error_message`, `status` fields.
DecisionRound has `emitted_at`, `answered_at`.

## Changes
- [ ] src/pylon/main.py: Add `/partials/activity` route
- [ ] src/pylon/templates/partials/activity.html (NEW): Chronological event list

## Proposed implementation

Query recent PhaseRuns and DecisionRounds, merge into chronological list. No separate activity table needed -- derive from existing data.

```python
@app.get("/partials/activity", response_class=HTMLResponse)
async def activity_partial(request: Request, db: AsyncSession = Depends(get_db)):
    recent_runs = (await db.execute(
        select(PhaseRun)
        .join(Pipeline)
        .join(Ticket)
        .options(selectinload(PhaseRun.pipeline).selectinload(Pipeline.ticket))
        .order_by(PhaseRun.created_at.desc())
        .limit(50)
    )).scalars().all()

    events = []
    for run in recent_runs:
        slug = run.pipeline.ticket.slug
        assignee = run.pipeline.ticket.assignee
        pid = run.pipeline_id
        if run.started_at:
            events.append({"ts": run.started_at, "type": "started", "slug": slug,
                           "assignee": assignee, "msg": f"{run.phase} started", "pid": pid})
        if run.completed_at and run.status == "completed":
            events.append({"ts": run.completed_at, "type": "completed", "slug": slug,
                           "assignee": assignee, "msg": f"{run.phase} completed", "pid": pid})
        if run.completed_at and run.status == "failed":
            events.append({"ts": run.completed_at, "type": "failed", "slug": slug,
                           "assignee": assignee, "msg": f"{run.phase} failed: {run.error_message or 'unknown'}", "pid": pid})

    events.sort(key=lambda e: e["ts"], reverse=True)
    return templates.TemplateResponse("partials/activity.html", {
        "request": request, "events": events[:50],
    })
```

Template: simple list with timestamp, colored event type badge, slug link, message.

## Decisions
- [x] RESOLVED: Derive events from PhaseRun/DecisionRound timestamps, not a separate event log table

## Tests
Requirements: manual
- [ ] Activity feed shows recent events in reverse chronological order
- [ ] Failed events show in red
- [ ] Slug links navigate to ticket detail

## Commit
```
feat(dashboard): add activity feed partial

Activity feed derives events from PhaseRun timestamps. Shows phase
starts, completions, and failures in reverse chronological order.

- Register /partials/activity route
- Query recent PhaseRuns, merge into event list
- Color-coded event type badges (green/red/gray)
```

## Dependencies
blocked_by: wo-001
blocks: none

## After commit
- Update status/PROGRESS.md: check "Activity feed partial"
