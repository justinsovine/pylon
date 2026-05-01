# Pylon -- Asana Integration

## Role of Asana

Asana is the ticket source and status display for stakeholders. Pylon reads tickets from Asana, runs them through the pipeline, and writes status back. Asana stays the source of truth for what work exists. Pylon is the source of truth for pipeline state.

## Polling vs webhooks

### Option A: Polling (recommended for v1)

Celery beat task runs every 15 minutes during work hours, every 2 hours overnight.

```python
@app.task
def poll_asana():
    project_gid = settings.ASANA_PROJECT_GID
    tasks = asana_client.tasks.find_by_section(
        section_gid=settings.ASANA_READY_SECTION_GID,
        opt_fields="gid,name,notes,assignee.name,custom_fields"
    )
    for task in tasks:
        if not Ticket.query.filter_by(asana_gid=task["gid"]).first():
            create_ticket_and_pipeline(task)
```

Pros:
- No webhook infrastructure needed
- Works behind firewalls (no inbound connections)
- Idempotent (safe to run repeatedly)

Cons:
- Up to 15 min delay between Asana change and Pylon pickup
- Wastes API calls when nothing changed

### Option B: Webhooks (v2)

Asana sends POST to Pylon API when tasks change. Requires public URL or tunnel.

Only worth adding if the 15-minute delay becomes a problem. It won't for overnight batch processing.

## Asana project structure

### Board columns (sections)

```
Backlog → Ready for Dev → Investigating → Awaiting Decisions → Planning → Implementing → PR Ready → Done
```

Mapping to pipeline states:

| Asana Section | Pipeline Status | Who acts |
|--------------|----------------|----------|
| Backlog | (not in Pylon) | PM/lead |
| Ready for Dev | queued | Pylon picks up |
| Investigating | investigating | Agent |
| Awaiting Decisions | awaiting_decisions | Human (dashboard) |
| Planning | planning, critiquing | Agent + Human |
| Implementing | implementing, testing | Agent |
| PR Ready | pr_creating, completed | Human reviews PR |
| Done | (archived) | Merged |

Pylon moves tickets between sections as pipeline state changes.

### Custom fields on Asana tasks

| Field | Type | Values | Purpose |
|-------|------|--------|---------|
| pylon_status | enum | queued, running, parked, done, failed | Quick status without opening dashboard |
| pylon_repo | enum | esign, onboard, scriptus-web | Which repo this ticket targets |
| pylon_pr | text | URL | Link to PR when created |
| pylon_decisions_pending | number | 0-N | How many decisions waiting for human |

### What Pylon reads from Asana

- Task title and description (becomes investigation context)
- Assignee (maps to dev: justin, tanya, michael)
- Section/column (determines if task is ready for pickup)
- Tags (bug, feature, refactor -- may influence pipeline behavior)
- Subtasks (if using subtask-per-phase pattern)
- Comments (additional context for investigation)

### What Pylon writes to Asana

- Section moves (ticket progresses through board)
- Custom field updates (pylon_status, pylon_pr, pylon_decisions_pending)
- Comments at phase transitions:

```
--- Pylon: Investigation Complete ---
Investigated 34 files across 4 directories.
Key findings: 3 existing forms use server-side validation, no client-side library installed.
2 security considerations flagged.

Investigation notes: [link to notes or inline summary]
Decisions pending: 3
Dashboard: [link to decision view]
```

- Assignee changes: if a ticket is assigned to a dev, Pylon keeps that assignment. Pylon never reassigns.

## State synchronization

### Pylon -> Asana (primary direction)

Pipeline state changes trigger Asana updates. Celery task:

```python
@app.task
def sync_to_asana(pipeline_id):
    pipeline = Pipeline.query.get(pipeline_id)
    ticket = pipeline.ticket
    
    section = STATUS_TO_SECTION[pipeline.status]
    asana_client.tasks.update(ticket.asana_gid, {
        "custom_fields": {
            PYLON_STATUS_FIELD: pipeline.status,
            PYLON_PR_FIELD: pipeline.pr_url or "",
            PYLON_DECISIONS_FIELD: count_pending_decisions(pipeline),
        }
    })
    
    if section != get_current_section(ticket.asana_gid):
        move_to_section(ticket.asana_gid, section)
```

### Asana -> Pylon (secondary)

Polling picks up:
- New tasks in "Ready for Dev" (creates pipeline)
- Task description changes (updates ticket.description, may trigger re-investigation)
- Task reassignment (updates ticket.assignee)
- Task deletion/completion in Asana (cancels pipeline if running)

### Conflict resolution

If someone moves a ticket in Asana while Pylon is running it:
- Pylon's next sync overwrites the section (Pylon wins on pipeline state)
- If ticket is moved to "Done" manually in Asana, Pylon cancels the pipeline
- If ticket is moved back to "Backlog", Pylon cancels the pipeline

## Asana API client

Thin wrapper. Not a full SDK integration.

```python
class AsanaClient:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://app.asana.com/api/1.0"
        self.session = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
    
    async def get_section_tasks(self, section_gid, fields=None):
        ...
    
    async def update_task(self, task_gid, data):
        ...
    
    async def move_to_section(self, task_gid, section_gid):
        ...
    
    async def add_comment(self, task_gid, text):
        ...
```

Rate limit: Asana allows 1500 requests/minute. Pylon will use maybe 50/hour. Not a concern.

## Multi-repo handling

Tickets target specific repos. The `pylon_repo` custom field tells Pylon which repo to investigate.

If not set, Pylon infers from:
1. Asana project (if you have separate projects per repo)
2. Task tags (tagged "esign" or "onboard")
3. Task title/description keywords

If ambiguous, Pylon creates the ticket but marks pipeline as awaiting_decisions with a decision: "Which repo does this ticket target?"

## Per-dev batching

The overnight batch groups tickets by assignee:

```python
@app.task
def overnight_batch():
    ready_tickets = poll_new_tickets()
    
    by_assignee = group_by(ready_tickets, key=lambda t: t.assignee)
    
    for assignee, tickets in by_assignee.items():
        # Max 4 per dev per night
        batch = tickets[:4]
        
        for ticket in batch:
            create_pipeline(ticket)
            run_phase.delay(ticket.pipeline.id, "investigate")
    
    # Notify when all investigations complete
    chord(
        [run_phase.s(t.pipeline.id, "investigate") for t in all_batched],
        notify_investigations_complete.s()
    )()
```
