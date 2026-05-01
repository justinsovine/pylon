# Pylon -- Dashboard

## Screens

Five screens. One primary workflow, four supporting.

### 1. Pipeline Board (home screen)

Kanban-style view of all active pipelines. Columns map to pipeline phases.

```
┌─────────────┬──────────────┬──────────────┬──────────────┬──────────────┬────────────┐
│ Queued      │ Investigating│ Decisions    │ Planning     │ Implementing │ PR Ready   │
│             │              │              │              │              │            │
│ ┌─────────┐ │ ┌──────────┐ │ ┌──────────┐ │              │ ┌──────────┐ │ ┌────────┐ │
│ │worker   │ │ │offer-    │ │ │profile-  │ │              │ │webhook-  │ │ │sms-    │ │
│ │export   │ │ │letter    │ │ │export    │ │              │ │auth-fix  │ │ │builder │ │
│ │         │ │ │          │ │ │          │ │              │ │          │ │ │        │ │
│ │onboard  │ │ │onboard   │ │ │3 pending │ │              │ │stage 2/5 │ │ │View PR │ │
│ │@tanya   │ │ │@justin   │ │ │@justin   │ │              │ │@michael  │ │ │@tanya  │ │
│ └─────────┘ │ └──────────┘ │ └──────────┘ │              │ └──────────┘ │ └────────┘ │
│             │              │              │              │              │            │
│             │ ┌──────────┐ │ ┌──────────┐ │              │              │            │
│             │ │form-     │ │ │audit-    │ │              │              │            │
│             │ │builder   │ │ │logging   │ │              │              │            │
│             │ │          │ │ │          │ │              │              │            │
│             │ │scriptus  │ │ │1 pending │ │              │              │            │
│             │ │@michael  │ │ │@tanya    │ │              │              │            │
│             │ └──────────┘ │ └──────────┘ │              │              │            │
└─────────────┴──────────────┴──────────────┴──────────────┴──────────────┴────────────┘
```

Each card shows:
- Ticket slug (linked to Asana)
- Repo badge (esign / onboard / scriptus-web)
- Assignee
- Phase-specific info:
  - Investigating: progress message from status.json
  - Decisions: count of pending decisions, "Answer" button
  - Implementing: stage N of M
  - PR Ready: link to GitHub PR

Filters:
- By assignee (each dev sees their own tickets by default)
- By repo
- By status (active / completed / failed)

### 2. Decision View (the core interaction)

Where devs spend most of their time. Shows all pending decisions for a ticket.

```
┌────────────────────────────────────────────────────────────────────┐
│  profile-export — Refine (Round 1 of 2)                          │
│  onboard · @justin · 3 decisions                                  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1. Export format                                             │  │
│  │                                                              │  │
│  │ Which format should the worker profile export use?           │  │
│  │                                                              │  │
│  │ Context: Investigation found existing exports in onboard     │  │
│  │ use CSV via League\Csv. Scriptus-web uses XLSX via           │  │
│  │ box/spout. No shared export library across repos.            │  │
│  │                                                              │  │
│  │ ○ A: CSV (League\Csv)                             ★ rec     │  │
│  │   Consistent with onboard. Simpler. No new dependency.      │  │
│  │                                                              │  │
│  │ ○ B: XLSX (PhpSpreadsheet)                                  │  │
│  │   Richer formatting. Larger dependency. Overkill for         │  │
│  │   flat worker data.                                          │  │
│  │                                                              │  │
│  │ ○ C: Both (user chooses at export time)                     │  │
│  │   Most flexible. More UI work. More code to maintain.       │  │
│  │                                                              │  │
│  │ Note: _______________________________________________        │  │
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 2. Export scope                                              │  │
│  │ ...                                                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 3. Email notification on export complete                     │  │
│  │ ...                                                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ [Accept All Recommendations]    [Submit Answers]           │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  Decision history (this ticket):                                   │
│  └ Round 0 (investigate): no decisions                             │
└────────────────────────────────────────────────────────────────────┘
```

Key interactions:
- Click option to select
- Optional note field per decision (freeform context)
- "Accept All Recommendations" button (one click, takes agent's picks)
- "Submit Answers" posts all answers, triggers next round or next phase
- Can answer partial (save draft, come back later)
- Decision cards are collapsible (scan question list first, then expand to read context)

### 3. Ticket Detail

Deep view of one pipeline. Shows full history.

```
┌────────────────────────────────────────────────────────────────────┐
│  profile-export                                                    │
│  onboard · @justin · Asana #1234567                               │
│  Branch: feature/profile-export                                    │
│  PR: (not yet created)                                             │
│                                                                    │
│  Phase Progress                                                    │
│  ━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░░░░░░░░                        │
│  investigate ✓ · refine ● · plan ○ · critique ○ · implement ○     │
│                                                                    │
│  ┌─ Investigate (Pass 1) ── completed 2:34 AM ──────────────────┐ │
│  │ Scanned 34 files. Found 3 existing export patterns.           │ │
│  │ Key risk: no shared export service, each module rolls its own.│ │
│  │ [View investigation.md]                                       │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌─ Refine (Round 1) ── awaiting decisions ─────────────────────┐ │
│  │ 3 decisions pending                                           │ │
│  │ [Go to decisions]                                             │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Worker Sessions                                                   │
│  #1  investigate  completed  2:12 AM - 2:34 AM  (22 min)         │
│  #2  refine       running    2:35 AM - 2:38 AM  (3 min)          │
│                                                                    │
│  Files Modified (so far): none                                     │
│  Notes: [investigation.md] [.pylon/round-1.json]                  │
└────────────────────────────────────────────────────────────────────┘
```

### 4. Activity Feed

Chronological log across all pipelines. What happened while you were away.

```
┌────────────────────────────────────────────────────────────────────┐
│  Activity                                              Filter: All │
│                                                                    │
│  9:23 AM  justin answered 3 decisions on profile-export           │
│  9:20 AM  webhook-auth-fix implement stage 2/5 complete           │
│  2:38 AM  profile-export refine emitted 3 decisions               │
│  2:34 AM  profile-export investigation complete (22 min)          │
│  2:33 AM  audit-logging investigation complete (19 min)           │
│  2:31 AM  offer-letter investigation complete (21 min)            │
│  2:12 AM  overnight batch started: 4 tickets                      │
│  yesterday                                                         │
│  5:45 PM  sms-builder PR #1082 opened                             │
│  5:30 PM  sms-builder implement complete (all 5 stages)           │
│  ...                                                               │
└────────────────────────────────────────────────────────────────────┘
```

Filterable by: dev, repo, event type (decisions, completions, failures).

### 5. Settings

- Asana connection (project ID, API token)
- Repo paths and git remotes
- Claude account configuration
- Worker timeout defaults per phase
- Notification preferences (Slack webhook, email, push)
- Team members (name, email, Asana user GID)

## HTMX implementation notes

### Real-time updates without React

Pipeline board polls via HTMX every 10 seconds:

```html
<div hx-get="/board" hx-trigger="every 10s" hx-swap="innerHTML">
  <!-- board cards -->
</div>
```

Decision submission:

```html
<form hx-post="/api/decisions/rounds/{{round_id}}/answers" 
      hx-target="#ticket-{{ticket_slug}}" 
      hx-swap="outerHTML">
  <!-- decision cards with radio buttons -->
  <button type="submit">Submit Answers</button>
</form>
```

SSE for instant updates (optional, upgrade from polling):

```html
<div hx-ext="sse" sse-connect="/events" sse-swap="pipeline-update">
  <!-- board updates instantly when pipeline state changes -->
</div>
```

FastAPI serves SSE via Postgres LISTEN/NOTIFY:

```python
@app.get("/events")
async def event_stream(request: Request):
    async def generate():
        async for notification in pg_listen("pipeline_events"):
            yield f"event: pipeline-update\ndata: {notification.payload}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Mobile considerations

HTMX pages are naturally responsive. Decision cards stack vertically on mobile. Core flow (see decisions, tap option, submit) works on phone without any special mobile work.

Add to home screen (PWA manifest) for app-like experience without building a native app.

### Styling

Tailwind CSS served from CDN. Same utility classes the team uses in onboard/scriptus-web. No build step.

Dashboard has a utilitarian aesthetic. Cards, tables, status badges. Not a marketing site. Readability and information density over visual polish.

Color coding:
- Green: completed phases, answered decisions
- Yellow/amber: awaiting decisions, parked
- Blue: running, in progress
- Red: failed, timed out
- Gray: queued, not started
