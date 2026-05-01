# Pylon

Async feature development pipeline that runs Claude Code workers against Asana tickets and surfaces decision points in a web dashboard for human review.

## The problem

Three developers. Three Laravel repos. Tickets in Asana. Claude Code helps interactively but it's single-player, synchronous, and terminal-bound. The human's actual value is concentrated in two moments: making scope/approach decisions and vetting the plan. Everything else is agent work.

## How it works

Agents run phases autonomously. When they hit a decision point, they park the work and surface the question in a dashboard. The human answers when ready. The agent resumes. PRs appear.

```
Overnight    Agents investigate next batch of tickets (4 per dev)
Morning      Devs open dashboard, answer refine decisions (~5 min each)
             Agents plan all tickets
             Devs review plans, answer critique questions (~5 min each)
             Agents implement, test, open PRs
Afternoon    Devs review PRs, merge
```

### Pipeline phases

```
investigate → refine → plan → critique → implement → test → pr
                ↑          ↑
           human input  human input
```

Phases without decision points run unattended. Phases with decision points park and wait for human answers via the dashboard.

### Decision batching

Instead of one-at-a-time Q&A, agents emit all independent decisions in a single round. Dependent decisions come in subsequent rounds. Most features need 2 rounds, not 7 individual waits.

## Stack

| Layer | Choice |
|-------|--------|
| Backend | Python / FastAPI |
| Database | PostgreSQL 16 (JSONB for decisions, LISTEN/NOTIFY for events) |
| Queue | Celery + Redis |
| Frontend | HTMX + Jinja2 + Tailwind CSS + Alpine.js |
| Worker harness | asyncio subprocess managing Claude Code CLI |
| Deployment | Docker Compose |

## Project structure

```
pylon/
├── src/pylon/
│   ├── main.py              # FastAPI app, template routes
│   ├── config.py             # Settings via pydantic-settings
│   ├── database.py           # SQLAlchemy async engine + session
│   ├── models.py             # ORM models (tickets, pipelines, decisions, workers)
│   ├── schemas.py            # Pydantic request/response types
│   ├── api/
│   │   ├── pipelines.py      # CRUD + cancel/retry endpoints
│   │   ├── decisions.py      # Pending decisions, answer submission
│   │   ├── workers.py        # Worker status, kill
│   │   └── internal.py       # Worker IPC (phase started/completed/failed)
│   ├── tasks/
│   │   ├── celery_app.py     # Celery config, beat schedule
│   │   ├── pipeline.py       # run_phase task with retry/timeout
│   │   ├── asana.py          # Asana polling + API client
│   │   └── maintenance.py    # Stale worker detection, worktree cleanup
│   ├── harness/
│   │   ├── worker.py         # Spawn/monitor/kill Claude Code processes
│   │   └── ipc.py            # Read/write .pylon/ directory files
│   ├── templates/            # Jinja2 + HTMX (board, decisions, ticket, activity)
│   └── static/
├── tests/
│   ├── conftest.py           # Async DB fixtures, test client
│   ├── factories.py          # Test data factories
│   ├── test_api/             # API endpoint tests
│   ├── test_tasks/           # Celery task tests
│   └── test_harness/         # IPC unit tests
├── alembic/                  # Database migrations (async)
├── docker-compose.yml        # Postgres + Redis + API + Worker + Beat + Flower
├── Dockerfile
├── pyproject.toml            # uv project config, ruff/pyright settings
└── justfile                  # Task runner
```

## Setup

```bash
# Install dependencies
uv sync --all-extras

# Copy and configure environment
cp .env.example .env
# Edit .env with your Asana token, Slack webhook, etc.

# Start infrastructure
docker compose up -d db redis

# Create databases
createdb pylon
createdb pylon_test

# Run migrations
just migrate

# Start the API
just dev

# In separate terminals:
just worker
just beat
just flower    # optional: Celery monitoring at localhost:5555
```

Dashboard at `http://localhost:8000`. Flower at `http://localhost:5555`.

Or run everything in Docker:

```bash
docker compose up -d
```

## Development

```bash
just test              # run tests
just lint              # ruff + pyright
just fmt               # auto-format
just migration "msg"   # generate migration from model changes
just rollback          # undo last migration
```

## Design docs

Detailed design documentation lives alongside the code:

| Doc | Contents |
|-----|----------|
| [CONCEPT.md](CONCEPT.md) | Problem statement, core concepts, daily rhythm |
| [BRANDING.md](BRANDING.md) | Relationship between /pylon and /feature skills |
| [TECH.md](TECH.md) | Stack decisions with tradeoff analysis |
| [TOOLING.md](TOOLING.md) | Every tool in the project and why it was chosen |
| [DATA-MODEL.md](DATA-MODEL.md) | PostgreSQL schema, key queries, entity relationships |
| [DECISION-PROTOCOL.md](DECISION-PROTOCOL.md) | Round-based Q&A contract, JSON schemas, edge cases |
| [WORKER-LIFECYCLE.md](WORKER-LIFECYCLE.md) | Spawn, monitor, timeout, retry, cleanup flows |
| [ASANA-INTEGRATION.md](ASANA-INTEGRATION.md) | Polling strategy, board columns, state machine |
| [DASHBOARD.md](DASHBOARD.md) | Screen wireframes, HTMX implementation, interaction patterns |
| [API-SURFACE.md](API-SURFACE.md) | All REST endpoints, auth model, notifications |
| [FEATURE-SKILL-MODS.md](FEATURE-SKILL-MODS.md) | /pylon skill phase design and file protocol |

## Relationship to /feature

/pylon and /feature are independent skills. /pylon was inspired by /feature's phase structure but is a clean fork designed for non-interactive, dashboard-based execution. /feature remains a terminal-first interactive tool. They may diverge over time.
