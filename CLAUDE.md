# CLAUDE.md

Async feature development pipeline. Runs Claude Code workers against Asana tickets, surfaces decision points in an HTMX dashboard. Internal tool for 3 developers across 3 Laravel repos at EdocServiceInc.

## Quick orientation

Read these first when resuming work:
- `status/PROGRESS.md` -- what's built, what's wired, what's TODO (with percentages)
- `status/backlog/critical-path.md` -- must-do items for first end-to-end loop
- `status/DECISIONS.md` -- decisions already made (don't re-litigate)
- `status/OPEN-QUESTIONS.md` -- undecided items needing human input

Design docs (top-level .md files): CONCEPT, TECH, TOOLING, DATA-MODEL, DECISION-PROTOCOL, WORKER-LIFECYCLE, ASANA-INTEGRATION, DASHBOARD, API-SURFACE, FEATURE-SKILL-MODS (skill phase design), PRE-INVESTIGATION, BRANDING.

## Stack

- Python 3.12, FastAPI, SQLAlchemy 2.0 async + asyncpg, Pydantic v2
- Celery + Redis (broker and result backend)
- PostgreSQL with JSONB for decision payloads
- HTMX + Jinja2 + Tailwind CDN + Alpine.js (no build step)
- Playwright + Chromium for browser testing
- tree-sitter-php for static analysis
- Docker Compose on shared `edoc` network

## Source layout

```
src/pylon/
  main.py              # FastAPI app, mounts routers, serves templates
  config.py            # Pydantic Settings (env-driven)
  database.py          # SQLAlchemy async engine + session factory
  models.py            # 7 ORM models: Ticket, Pipeline, PhaseRun, DecisionRound, Decision, Answer, WorkerSession
  schemas.py           # All Pydantic request/response types
  api/
    pipelines.py       # CRUD, filtering by assignee/status/repo
    decisions.py       # Pending decisions query, answer batch submission
    workers.py         # Worker listing, psutil-based process kill
    internal.py        # IPC endpoints with API key auth, phase state machine
  tasks/
    celery_app.py      # Celery config, beat schedule
    pipeline.py        # run_phase task, overnight_batch, keyword extraction
    asana.py           # AsanaClient (httpx), poll_asana task
    maintenance.py     # detect_stale_workers, cleanup_worktrees (stubs)
  harness/
    worker.py          # spawn_worker, kill_worker, account rotation
    ipc.py             # File-based IPC: config, answers, result, round files
    preinvestigate.py  # Orchestrator: runs all analyzers in parallel
    browser.py         # Playwright browser testing harness
    cli.py             # CLI entry points: check-tools, pre-investigate
    analyzers/
      ctags.py         # universal-ctags JSON parsing
      ripgrep.py       # rg keyword search
      tree_sitter_php.py  # PHP class hierarchy + model extraction
      php_routes.py    # Route extraction (artisan live, regex fallback)
      phpstan.py       # PHPStan JSON output parsing
      docker_exec.py   # Docker exec wrapper for container commands
      mailpit.py       # Mailpit HTTP API client
  templates/           # Jinja2 templates (base, board, decisions, ticket, activity)
  static/              # CSS/JS if needed
tests/
  conftest.py          # Async DB fixtures, test client
  factories.py         # make_ticket, make_pipeline, make_phase_run, etc.
  test_api/            # Pipeline and decision endpoint tests
  test_harness/        # IPC and analyzer tests
  test_tasks/          # (empty, needs Celery task tests)
```

## Dev commands

```bash
just install          # uv sync --all-extras
just dev              # uvicorn with reload on :8000
just worker           # Celery worker (concurrency=3)
just beat             # Celery beat scheduler
just flower           # Flower dashboard on :5555
just up / just down   # Docker Compose
just test             # pytest
just lint             # ruff check + pyright
just fmt              # ruff format + fix
just migrate          # alembic upgrade head
just migration "msg"  # alembic autogenerate
just check-tools      # verify system tools installed
just pre-investigate <repo> <notes> [keywords...]
```

## Conventions

- Ruff for linting/formatting (line-length 100, py312 target)
- Pyright standard mode for type checking
- pytest-asyncio with `asyncio_mode = "auto"`
- SQLAlchemy 2.0 style (mapped_column, Mapped types, async sessions)
- Pydantic v2 style (model_config dict, not class Config)
- All API endpoints return Pydantic models
- Internal IPC endpoints require X-Pylon-Key header
- Phase order: investigate -> refine -> plan -> critique -> implement -> test -> pr

## Key design constraints

- Human stays in decision loop. No autonomous mode. Every ticket goes through human refine + critique.
- Phase-per-invocation. Each phase is a separate `claude -p` call. No persistent sessions.
- Decision batching in rounds. Independent decisions in round 1, dependent in round 2+.
- /pylon is a clean fork of /feature. They share no code and should not be merged.
- Celery for task queue. Don't suggest alternatives.
- File-based IPC via .pylon/ directory in worktree (status.json, result.json, decisions/round-N.json).

## What's wired vs not

Models, schemas, and API endpoint signatures are complete. The gap is wiring: API endpoints don't dispatch Celery tasks yet, Celery tasks don't call internal API on completion, workers don't create git worktrees, and the /pylon skill phase files don't exist. See `status/backlog/critical-path.md` for the full list.

## Testing

```bash
just test                    # all tests
just test tests/test_api/    # API tests only
just test -k "tree_sitter"  # specific tests
```

Tests use async fixtures with a real test database (not mocks). Test factories in `tests/factories.py`.

## Target repos

Three Laravel 9 / PHP 8.1 apps under EdocServiceInc GitHub org:
- esign (36 controllers, 8 tests)
- onboard (33 controllers, 33 tests, most mature for Pylon)
- scriptus-web (34 controllers, 16 tests)

All use Laravel Sail, Tailwind, Livewire, Alpine.js. Connected via shared `edoc` Docker network.
