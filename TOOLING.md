# Pylon -- Tooling

## Project foundation

| Tool | Replaces | Why |
|------|----------|-----|
| **uv** | pip, pip-tools, venv, pyenv | Single tool for package management, virtualenv, lockfile. Resolves in seconds. |
| **Ruff** | flake8, black, isort | Linter + formatter. Single binary. Instant. |
| **pyright** | mypy | Stricter type checking, faster, better FastAPI/Pydantic inference. |
| **just** | Makefile | Task runner. `just dev`, `just test`, `just migrate`. Readable syntax. |
| **direnv** | manual env loading | Auto-loads .envrc on cd into project. |
| **pre-commit** | manual linting | Runs ruff + pyright before each commit. |

## Backend

| Tool | Purpose |
|------|---------|
| **FastAPI** | API framework. Async, auto-generated OpenAPI docs, Pydantic integration. |
| **SQLAlchemy 2.0** | ORM. Async support, type-safe queries. |
| **Alembic** | Database migrations. Auto-generates from model diffs. |
| **Pydantic v2** | Request/response validation. Built into FastAPI. |
| **httpx** | Async HTTP client. Asana API, Slack webhooks. |
| **uvicorn** | ASGI server. Auto-reload in dev. |
| **pydantic-settings** | Config from env vars. Type-safe settings. |

## Queue

| Tool | Purpose |
|------|---------|
| **Celery** | Task queue. Retry, timeout, chord/chain, rate limiting. |
| **Redis** | Celery broker + result backend. |
| **Flower** | Celery web monitor. Active tasks, failures, worker health. |
| **celery-beat** | Periodic task scheduler. Overnight batch, Asana polling. |

## Database

| Tool | Purpose |
|------|---------|
| **PostgreSQL 16** | Primary database. JSONB for decisions, LISTEN/NOTIFY for events. |
| **asyncpg** | Fastest async Postgres driver. Used by SQLAlchemy async engine. |
| **pgcli** | Better CLI than psql. Autocomplete, syntax highlighting. |

## Frontend

| Tool | Purpose |
|------|---------|
| **HTMX** | Dynamic HTML without JS framework. Polling, SSE, form submission. |
| **Jinja2** | Server-side templates. Built into Starlette/FastAPI. |
| **Tailwind CSS (CDN)** | Styling. No build step. Team knows it from Laravel. |
| **Alpine.js** | Light interactivity. Collapsible cards, draft state. Team knows it from onboard. |

## Worker harness

| Tool | Purpose |
|------|---------|
| **asyncio subprocess** | Spawn and manage Claude Code processes. |
| **watchfiles** | Watch .pylon/ directory for status/decision file changes. |
| **psutil** | Process health checks. PID alive, memory, CPU. |

## Testing

| Tool | Purpose |
|------|---------|
| **pytest** | Test framework. |
| **pytest-asyncio** | Async test support for FastAPI endpoints. |
| **factory-boy** | Test data factories. `PipelineFactory.create(status="awaiting_decisions")`. |
| **httpx** | FastAPI test client. |
| **testcontainers** | Real Postgres + Redis in Docker per test run. |

## Infrastructure

| Tool | Purpose |
|------|---------|
| **Docker Compose** | Local stack: Postgres, Redis, API, workers, Flower. |
| **Docker** | Container images for API and worker services. |

## Intentionally skipped

| Tool | Why skipped |
|------|------------|
| Poetry | uv is faster, simpler, better lockfile |
| Django | Too opinionated for orchestrator. FastAPI is lighter. |
| SQLModel | Immature. SQLAlchemy 2.0 is proven. |
| Dramatiq | Celery alternative, but user wants Celery |
| React | HTMX sufficient for v1. Upgrade path clear. |
| Kubernetes | 3 users, one machine. Docker Compose ceiling is far away. |
| Terraform | No cloud infra to manage |
