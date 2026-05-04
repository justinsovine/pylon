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
                ↑                ↑                    ↑
           human input      human input          human input
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

All dev work runs in Docker. No local venv needed.

### Prerequisites

- Docker Engine with the Compose plugin, **or** standalone `docker-compose` (see note below)
- `mkcert` for local TLS
- `local-proxy` running on the shared `edoc` Docker network

> **Docker Compose on macOS via Homebrew:** If you installed Docker Engine via Homebrew rather than Docker Desktop, the `docker compose` plugin may not be available. Use `docker-compose` (standalone) instead. Verify with `docker-compose version`.

### 1. Shared Docker network

```bash
docker network create edoc
```

Skip if already exists (it's shared with `local-proxy` and the Laravel apps).

### 2. Environment

```bash
cp .env.example .env
```

Edit `.env` -- values that must change:

| Variable | Notes |
|----------|-------|
| `REPOS_BASE_PATH` | Absolute path to your `edoc` directory, e.g. `/Users/<you>/code/edoc` |
| `NOTES_BASE_PATH` | Absolute path to `edoc/notes`, e.g. `/Users/<you>/code/edoc/notes` |
| `REPO_PATHS` | Override if your scriptus repo is at `scriptus/web` (not `scriptus-web`): `{"esign": "esign", "onboard": "onboard", "scriptus-web": "scriptus/web"}` |
| `PYLON_INTERNAL_KEY` | Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `PYLON_SECRET_KEY` | Same as above |
| `ASANA_TOKEN` | Personal access token from Asana settings |
| `ASANA_PROJECT_GID` | Numeric ID from the Asana project URL |
| `ASANA_READY_SECTION_GID` | Numeric ID of the section Pylon polls for new tickets |

Asana GIDs can be left blank -- Pylon runs without them, you just won't get automatic ticket ingestion.

### 3. Build and start

```bash
docker-compose build
docker-compose up -d
```

Migrations run automatically on API startup. Verify with:

```bash
docker-compose logs -f api
```

### 4. Test database

```bash
docker-compose exec db psql -U pylon -c "CREATE DATABASE pylon_test;"
```

### 5. local-proxy + mkcert

Add a config file to `local-proxy/apps/pylon.conf`:

```nginx
server {
    listen 443 ssl;
    server_name pylon.test;
    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;
    resolver 127.0.0.11 valid=10s;
    location / {
        set $upstream pylon-api-1;
        proxy_pass http://$upstream:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 443 ssl;
    server_name flower.pylon.test;
    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;
    resolver 127.0.0.11 valid=10s;
    location / {
        set $upstream pylon-flower-1;
        proxy_pass http://$upstream:5555;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Add the domains to `local-proxy/docker-compose.yml` under `networks.edoc.aliases`:

```yaml
- pylon.test
- flower.pylon.test
```

Add them to the HTTP redirect `server_name` list in `local-proxy/default.conf`.

Regenerate the mkcert cert to include the new domains (include all existing domains plus the new ones):

```bash
cd local-proxy/certs
mkcert dev.esign.test mail.esign.test \
       dev.onboard.test mail.onboard.test \
       dev.scriptus.test mail.scriptus.test \
       pylon.test flower.pylon.test
mv "dev.esign.test+7.pem" cert.pem
mv "dev.esign.test+7-key.pem" key.pem
```

Add to `/etc/hosts`:

```
127.0.0.1 pylon.test flower.pylon.test
```

Restart local-proxy:

```bash
cd local-proxy && docker-compose restart
```

Dashboard at `https://pylon.test`. Flower at `https://flower.pylon.test`.

### 6. Run tests

```bash
docker-compose exec -e TEST_DATABASE_URL="postgresql+asyncpg://pylon:pylon@db:5432/pylon_test" api python -m pytest tests/ -q
```

Expected: 1 known failure (`test_create_pipeline` -- pre-existing MissingGreenlet issue, tracked in `grind/workorders/inbox/`).

## Development

```bash
# Logs
docker-compose logs -f api

# Run tests
docker-compose exec -e TEST_DATABASE_URL="postgresql+asyncpg://pylon:pylon@db:5432/pylon_test" api python -m pytest tests/ -q

# Migrations
docker-compose exec api alembic upgrade head
docker-compose exec api alembic revision --autogenerate -m "description"
docker-compose exec api alembic downgrade -1

# Rebuild after Dockerfile changes
docker-compose build --no-cache api
```

Host-side `just` commands (requires local venv via `uv sync --all-extras`):

```bash
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
