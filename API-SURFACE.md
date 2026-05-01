# Pylon -- API Surface

## Overview

FastAPI REST API. Serves the HTMX dashboard and provides endpoints for worker communication. Auth via session cookies for dashboard, API keys for worker/external access.

Base URL: `http://localhost:8000` (dev), `https://pylon.internal` or similar (prod).

## Endpoints

### Pipelines

```
GET    /api/pipelines
       Query params: ?assignee=justin&status=active&repo=onboard
       Returns: list of pipelines with ticket info and current phase
       Used by: dashboard board view

GET    /api/pipelines/{pipeline_id}
       Returns: full pipeline detail with phase runs, decisions, worker sessions
       Used by: dashboard ticket detail view

POST   /api/pipelines
       Body: { asana_gid, repo, assignee? }
       Creates: ticket (from Asana), pipeline, queues investigate phase
       Used by: manual trigger from dashboard, Asana poller
       Returns: { pipeline_id, ticket_slug }

POST   /api/pipelines/{pipeline_id}/cancel
       Cancels: running workers, marks pipeline cancelled
       Used by: dashboard

POST   /api/pipelines/{pipeline_id}/retry
       Retries: current failed phase
       Used by: dashboard

POST   /api/pipelines/{pipeline_id}/advance
       Force-advances: to next phase (skip current)
       Used by: dashboard (escape hatch when phase is stuck)
       Requires: confirmation flag { confirm: true }
```

### Decisions

```
GET    /api/decisions/pending
       Query params: ?assignee=justin
       Returns: all pending decisions across all pipelines for this user
       Used by: dashboard decisions queue, notification count badge

GET    /api/decisions/rounds/{round_id}
       Returns: round with all decisions and any existing answers
       Used by: dashboard decision view

POST   /api/decisions/rounds/{round_id}/answers
       Body: { answers: [{ decision_id, choice, note }], answered_by }
       Stores answers, checks if round complete
       If round complete: triggers next round or next phase
       Used by: dashboard decision form submission
       Returns: { round_status, next_action }

POST   /api/decisions/{decision_id}/answer
       Body: { choice, note, answered_by }
       Answer a single decision (for partial/incremental answering)
       Used by: dashboard, /pylon CLI
```

### Workers

```
GET    /api/workers
       Query params: ?status=running
       Returns: all active worker sessions with health info
       Used by: dashboard, monitoring

GET    /api/workers/{worker_id}/logs
       Returns: recent stdout/stderr from worker process
       Used by: dashboard ticket detail, debugging

POST   /api/workers/{worker_id}/kill
       Kills: worker process (SIGTERM then SIGKILL)
       Used by: dashboard emergency stop
```

### Worker IPC (called by worker harness, not dashboard)

```
POST   /api/internal/phase-started
       Body: { pipeline_id, phase, worker_id }
       Updates: pipeline status, phase_run status
       Auth: internal API key

POST   /api/internal/decisions-emitted
       Body: { pipeline_id, phase, round_number, decisions: [...] }
       Stores: decision round and individual decisions in DB
       Updates: pipeline status to awaiting_decisions
       Triggers: notification to assigned dev
       Auth: internal API key

POST   /api/internal/phase-completed
       Body: { pipeline_id, phase, result: {...} }
       Updates: phase_run status, pipeline current_phase
       Triggers: next phase dispatch (if non-decision phase next)
       Auth: internal API key

POST   /api/internal/phase-failed
       Body: { pipeline_id, phase, error, retry_safe }
       Updates: phase_run status, worker_session status
       Triggers: auto-retry if retry_safe and retries remaining
       Auth: internal API key

POST   /api/internal/progress
       Body: { pipeline_id, phase, progress, message }
       Updates: status display for dashboard polling
       Auth: internal API key
```

### Activity

```
GET    /api/activity
       Query params: ?assignee=justin&repo=onboard&limit=50&since=2026-05-01T00:00:00Z
       Returns: chronological event log
       Used by: dashboard activity feed
```

### Asana

```
POST   /api/asana/sync
       Triggers: immediate Asana poll (instead of waiting for next scheduled poll)
       Used by: dashboard "refresh from Asana" button

GET    /api/asana/sections
       Returns: Asana board sections with task counts
       Used by: settings page, diagnostics
```

### Dashboard HTML (HTMX)

```
GET    /                          → board view (home)
GET    /tickets/{slug}            → ticket detail
GET    /tickets/{slug}/decisions  → decision view for active round
GET    /activity                  → activity feed
GET    /settings                  → settings page

# HTMX partials (return HTML fragments, not full pages)
GET    /partials/board            → board cards (polled every 10s)
GET    /partials/ticket/{slug}    → ticket detail content
GET    /partials/decisions/{round_id} → decision cards
GET    /partials/activity         → activity feed items
GET    /partials/badge            → notification count badge
```

## Auth

### Dashboard (human users)

Session-based auth. Simple for 3 users.

v1: Hardcoded users in config. Login with email + password. Session cookie.

```python
USERS = {
    "justin": { "email": "justin@intellect37.com", "password_hash": "..." },
    "tanya": { "email": "...", "password_hash": "..." },
    "michael": { "email": "...", "password_hash": "..." },
}
```

v2: OAuth via Google Workspace (if EdocServiceInc uses Google) or Clerk (if reusing from esign).

### Internal API (worker harness)

Static API key in environment variable. Workers run on the same machine, so this is mostly preventing accidental external access, not real security boundary.

```python
PYLON_INTERNAL_API_KEY = os.environ["PYLON_INTERNAL_KEY"]

@app.middleware("http")
async def check_internal_auth(request, call_next):
    if request.url.path.startswith("/api/internal/"):
        key = request.headers.get("X-Pylon-Key")
        if key != PYLON_INTERNAL_API_KEY:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
    return await call_next(request)
```

## Notifications

### When to notify

| Event | Notify | Channel |
|-------|--------|---------|
| Decisions pending | Assigned dev | Slack DM + dashboard badge |
| All investigations complete | All devs in batch | Slack channel |
| Pipeline failed | Assigned dev | Slack DM |
| PR opened | Assigned dev | Slack DM + Asana comment |
| Worker timed out | Assigned dev | Slack DM |

### Slack integration

Webhook URL in settings. Simple POST:

```python
async def notify_slack(channel_or_user, message):
    await httpx.post(settings.SLACK_WEBHOOK_URL, json={
        "channel": channel_or_user,
        "text": message,
        "unfurl_links": False,
    })
```

### Dashboard badge

Top-right corner shows count of pending decisions. Polls every 30s via HTMX.

```html
<span hx-get="/partials/badge" hx-trigger="every 30s" class="badge">
  3
</span>
```

## Error responses

Standard format across all endpoints:

```json
{
  "error": "pipeline_not_found",
  "message": "No pipeline with ID abc-123",
  "status": 404
}
```

## Rate limiting

Not needed for v1 (3 users, internal tool). Add if it ever becomes external.

## OpenAPI docs

FastAPI auto-generates at `/docs` (Swagger UI) and `/redoc`. Free documentation for the internal API.
