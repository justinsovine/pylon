# Pylon -- Tech Stack Analysis

## Layers

```
┌─────────────────────────────────────────┐
│  Dashboard (frontend)                   │
├─────────────────────────────────────────┤
│  API Server (backend)                   │
├──────────────┬──────────────────────────┤
│  Database    │  Queue / Pub-sub         │
├──────────────┴──────────────────────────┤
│  Worker Harness (manages Claude Code)   │
├─────────────────────────────────────────┤
│  Claude Code (the actual agent)         │
├─────────────────────────────────────────┤
│  Git Worktrees (isolation per ticket)   │
└─────────────────────────────────────────┘
```

Seven layers. Each has a decision.


## 1. Backend -- the API server

This is the brain. Manages pipeline state, serves decisions to dashboard, receives answers, dispatches workers.

### Option A: Python / FastAPI

Pros:
- Best subprocess management in any language (asyncio.create_subprocess)
- FastAPI has native websocket support, auto-generated OpenAPI docs
- Pydantic models for decision point schema validation
- Celery/RQ/Dramatiq for task queue if needed later
- Claude's Anthropic SDK is Python-first

Cons:
- Not what the team writes daily (PHP/Laravel)
- Another language in the stack

### Option B: Node.js / Fastify

Pros:
- child_process / execa for subprocess management
- Native websocket ecosystem (ws, socket.io)
- Same language as potential React frontend
- Lighter runtime than Python

Cons:
- subprocess management less mature than Python
- callback/promise patterns get messy with long-running workers

### Option C: PHP / Laravel

Pros:
- Team knows it cold
- Laravel Horizon for queue management (Redis-backed)
- Livewire for real-time dashboard without separate frontend
- One language across Pylon and the target repos

Cons:
- PHP subprocess management is painful (symfony/process works but clunky)
- Long-running worker processes fight against PHP's request lifecycle
- Websockets need additional infra (Laravel Reverb or Pusher)
- Wrong tool for an orchestration/subprocess app

### Recommendation: **Python / FastAPI**

This is an orchestration tool, not a web app. Subprocess management is the core mechanic. Python wins here by a wide margin. The team doesn't need to maintain Pylon like they maintain the Laravel repos -- it's infrastructure, not product code.


## 2. Database

Stores: pipeline state, decision points, decision history, worker status, ticket metadata.

### Option A: PostgreSQL

Pros:
- JSONB for flexible decision point payloads
- Row-level locking for concurrent worker updates
- LISTEN/NOTIFY for real-time events (worker completed, decision answered)
- Scales to any volume this project will hit
- Good migration tooling (Alembic with SQLAlchemy)

### Option B: SQLite

Pros:
- Zero infrastructure. Single file.
- WAL mode handles moderate concurrent writes
- Good enough for 3 users and ~12 tickets/day

Cons:
- Concurrent writes from multiple workers can contend
- No pub/sub (need separate mechanism for real-time)
- Harder to query remotely if dashboard runs elsewhere

### Recommendation: **PostgreSQL**

Already running it for the Laravel apps (or MySQL -- but Postgres is better for JSONB decision payloads). LISTEN/NOTIFY eliminates the need for a separate pub/sub layer for simple events. If you want to start lighter, SQLite works for prototype, swap to Postgres when adding real-time.


## 3. Queue / Worker dispatch

How the API tells workers to start, and how workers report back.

### Option A: Redis + simple pub/sub

Pros:
- Lightweight. Pub/sub for events, lists for job queue.
- Already common in Laravel stacks (team knows Redis)
- BullMQ (Node) or RQ (Python) as thin wrapper

Cons:
- No persistence for pub/sub (miss a message, it's gone)
- Need to build retry/dead-letter logic yourself

### Option B: Celery (Python) + Redis broker

Pros:
- Mature task queue with retry, timeout, rate limiting built in
- Flower dashboard for worker monitoring (free)
- chord/chain primitives for "investigate 4 tickets, then notify"

Cons:
- Heavy dependency for what might be 5 tasks/day
- Celery's complexity is famous

### Option C: PostgreSQL as queue (SKIP NOTHING pattern)

Pros:
- No additional infrastructure. SELECT FOR UPDATE SKIP LOCKED.
- Transactional with pipeline state (atomically update ticket status + dequeue)
- Good enough for low throughput (dozens of jobs/day, not thousands)

Cons:
- Polling-based (not instant, but 1s poll interval is fine for this scale)
- DIY retry/timeout logic

### Recommendation: **Celery + Redis**

Celery gives retry with backoff, hard/soft timeouts, Flower monitoring dashboard, and chord/chain primitives for "investigate 4 tickets in parallel, then notify." Redis as broker is lightweight and the team already knows it from Laravel. Yes it's more infra than needed for 12 jobs/day, but the primitives are worth learning and the abstraction is clean.


## 4. Frontend -- the dashboard

### Option A: React + Vite

Pros:
- Largest ecosystem for component libraries
- shadcn/ui for fast, good-looking dashboard components
- React Query for API state management
- Easy websocket integration

Cons:
- Separate build step, separate deploy
- Heavier than needed for what's mostly a list of cards

### Option B: Next.js

Pros:
- SSR for fast initial load
- API routes could replace some of FastAPI (but then you have two backends)
- App Router + Server Components for real-time

Cons:
- Overkill for an internal dashboard
- Deployment complexity (needs Node runtime)

### Option C: HTMX + Jinja templates (served from FastAPI)

Pros:
- No separate frontend build. FastAPI serves HTML directly.
- HTMX handles dynamic updates (polling, SSE for real-time)
- Extremely fast to build
- One deployment artifact

Cons:
- Harder to make feel "app-like" on mobile
- Complex interactions (drag-drop, inline editing) get hacky
- Ceiling is lower if this ever becomes a product

### Option D: Livewire (Laravel backend)

Pros:
- Team already knows Livewire from onboard
- Real-time built in
- Blade templates, familiar patterns

Cons:
- Requires Laravel backend (conflicts with Python recommendation)
- Couples dashboard to PHP

### Recommendation: **HTMX + Jinja for v1, React for v2**

v1 is an internal tool for 3 people. HTMX served from FastAPI means one app, one deploy, no frontend build pipeline. Decision cards, status lists, answer forms -- all trivially expressible in HTMX.

If Pylon becomes a product or the UI needs get complex, migrate the frontend to React. The API stays the same either way.


## 5. Worker harness -- how Pylon drives Claude Code

This is the most novel layer. No existing tooling does exactly this.

### The problem

Claude Code is a CLI tool designed for interactive terminal use. Pylon needs to:
1. Start a Claude Code process for a specific phase + ticket
2. Feed it the right prompt (with --notes, --asana flags)
3. Capture structured output (decision points, progress, artifacts)
4. Pause when a decision is needed
5. Resume with the human's answer
6. Handle timeouts and failures

### Approach A: Phase-per-invocation

Run each phase as a separate `claude -p` call. Between phases, the harness checks for decisions.

```python
# Harness pseudocode
async def run_pipeline(ticket):
    # Phase 1: investigate (no decisions, runs to completion)
    result = await run_claude(
        f"/feature investigate --notes={ticket.slug} --asana={ticket.gid}"
    )
    update_status(ticket, "investigate_complete")

    # Phase 2: refine (has decisions)
    # First pass: gather all decision points
    result = await run_claude(
        f"/feature refine --notes={ticket.slug} --output=json"
    )
    decisions = parse_decisions(result.stdout)
    
    # Park and wait for human
    for decision in decisions:
        save_decision(ticket, decision)
    update_status(ticket, "awaiting_refine_decisions")
    
    # ... harness sleeps until all decisions answered ...
    
    # Resume: feed decisions back
    result = await run_claude(
        f"/feature refine --notes={ticket.slug} --decisions={decisions_file}"
    )
```

Pros:
- Simple. Each invocation is stateless.
- Notes directory carries state between invocations.
- Failure = just re-run the phase.
- No long-lived processes to manage.

Cons:
- Each invocation starts cold (reads CLAUDE.md, notes, codebase).
- Refine phase currently does multi-turn Q&A -- hard to batch all decisions upfront.

### Approach B: Long-lived session with file-based IPC

Start Claude Code in a persistent session. Decision points written to a file. Harness watches for files, forwards to API, writes answer file. Claude Code polls for answer.

```
worker/
  ticket-123/
    decision-001.json     # Claude writes: question + options
    answer-001.json       # Harness writes: human's choice
    progress.json         # Claude updates: phase, stage, %
    error.json            # Claude writes on failure
```

Pros:
- Single session per ticket. Context stays warm.
- Multi-turn Q&A works naturally (write decision, wait, read answer, continue).
- Progress tracking is trivial (Claude updates a file).

Cons:
- Long-lived Claude Code sessions burn API credits while idle/waiting.
- Need to teach /feature phases to read/write these files.
- Process management complexity (what if Claude Code crashes mid-wait?).

### Approach C: Hybrid -- phase-per-invocation with decision batching

Modify refine/critique phases to emit ALL decisions at once (with recommendations), then a second invocation applies the answers.

Refine pass 1: "Here are the 7 decisions for this feature. I recommend X for each."
Human reviews all 7 in dashboard.
Refine pass 2: "Apply these 7 decisions" -- runs with answers as input.

Pros:
- No long-lived sessions.
- Human sees full decision landscape at once (better UX than one-at-a-time).
- Clean invocation boundary.

Cons:
- Decisions aren't always independent. Decision 3 might depend on decision 1.
- Requires modifying refine/critique phases to support batch mode.
- Some decisions only emerge after earlier ones are resolved.

### Recommendation: **Approach C (hybrid) with dependency chains**

Batch what can be batched. For dependent decisions, emit them in rounds:

```
Round 1: decisions 1-3 (independent)
  -> human answers
Round 2: decisions 4-5 (depend on round 1 answers)
  -> human answers
Round 3: decisions 6-7 (depend on round 2)
  -> human answers
```

Most features have 2-4 independent decisions and maybe 1-2 dependent ones. That's 2 rounds, not 7 individual waits. Good balance of UX and simplicity.

Each round is a separate Claude Code invocation. No long-lived sessions. Notes carry state.


## 6. Claude Code integration -- the --output=json contract

The /feature skill needs to know when it's running inside Pylon vs terminal.

### Detection

```
--pylon flag on /feature invocation
  OR
PYLON_WORKER=true environment variable
  OR
presence of .pylon/config.json in working directory
```

Recommend: environment variable. Harness sets it before spawning Claude Code. No skill modifications needed for detection.

### Structured output format

When PYLON_WORKER=true, phases write structured artifacts alongside their normal notes:

```
notes/ticket-slug/
  investigation.md                    # normal artifact
  implementation-plan.md              # normal artifact
  .pylon/
    status.json                       # {"phase": "refine", "progress": 0.4}
    decisions/
      round-1.json                    # emitted by agent
      round-1-answers.json            # written by harness
      round-2.json                    # emitted after round-1 answers applied
      round-2-answers.json
    result.json                       # {"status": "complete"} or {"status": "failed", "error": "..."}
```

Decision file schema:

```json
{
  "round": 1,
  "decisions": [
    {
      "id": "d001",
      "question": "Input validation approach",
      "context": "Investigation found 3 existing forms use server-side only...",
      "options": [
        {"key": "A", "label": "Server-side only", "tradeoff": "Simpler, consistent with codebase"},
        {"key": "B", "label": "Client + server", "tradeoff": "Better UX, more code to maintain"},
        {"key": "C", "label": "Progressive enhancement", "tradeoff": "Best UX, most complex"}
      ],
      "recommendation": "A",
      "recommendation_rationale": "Matches existing patterns in onboard. Forms use Livewire which validates server-side naturally.",
      "depends_on": null
    },
    {
      "id": "d002",
      "question": "Empty state design",
      "depends_on": null
    }
  ]
}
```

Answer file schema:

```json
{
  "round": 1,
  "answers": [
    {"id": "d001", "choice": "A", "note": ""},
    {"id": "d002", "choice": "B", "note": "Use the illustration from the brand kit"}
  ],
  "answered_by": "justin",
  "answered_at": "2026-05-01T09:23:00Z"
}
```


## 7. Deployment

### For v1 (internal tool, 3 users)

Run everything on one machine. Options:

**Your workstation:**
- Docker Compose: FastAPI + Postgres + workers
- Simplest. But machine needs to be on for overnight runs.

**The P40 server (when built):**
- Already planned as always-on local infra
- Claude Code workers don't need GPU (they call Anthropic API)
- GPU for OpenClaw, CPU for Pylon -- good separation

**Small VPS (Hetzner, $5-10/mo):**
- Always on, no local machine dependency
- Workers run Claude Code which calls Anthropic API (low CPU)
- Postgres runs locally on the VPS

### Recommendation: **Docker Compose on P40 server, VPS as fallback**

P40 server is already planned as always-on. Pylon runs alongside OpenClaw. If P40 build delays, a $7 Hetzner VPS runs everything.

```yaml
# docker-compose.yml (sketch)
services:
  api:
    build: ./api
    ports: ["8000:8000"]
    depends_on: [db]
    
  db:
    image: postgres:16
    volumes: ["pgdata:/var/lib/postgresql/data"]
    
  worker:
    build: ./worker
    volumes:
      - ./notes:/app/notes
      - worktrees:/app/worktrees
    deploy:
      replicas: 3
```


## Summary table

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | Python / FastAPI | Best subprocess management, async-native |
| Database | PostgreSQL | JSONB for decisions, LISTEN/NOTIFY for events |
| Queue | Celery + Redis | User wants it. Retry, timeout, Flower dashboard, chord/chain primitives. |
| Frontend v1 | HTMX + Jinja | One app, no build step, fast to ship |
| Frontend v2 | React + shadcn/ui | If it becomes a product |
| Worker harness | Phase-per-invocation, decision batching | No long-lived sessions, clean failure recovery |
| Claude integration | PYLON_WORKER env var + .pylon/ directory | Minimal skill modification |
| Deployment | Docker Compose on P40 server | Already planned infra |


## Build order

Phase 1 -- prove the loop works (1 week):
- FastAPI with 3 endpoints: create pipeline, get decisions, submit answer
- Worker harness that runs investigate + refine on one ticket
- HTMX page showing decisions
- Manual trigger, single ticket

Phase 2 -- batch and schedule (1 week):
- Asana polling
- Parallel workers (one per ticket)
- All phases wired
- Notification when decisions waiting

Phase 3 -- multi-user (1 week):
- Auth
- Per-dev ticket assignment
- Decision history
- PR links

Phase 4 -- polish:
- Mobile-friendly
- Progress tracking
- Error recovery UI
- Metrics
