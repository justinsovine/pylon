# Build Progress

Last updated: 2026-05-02 (Fixed 4 harness wiring gaps: ticket context, dead flags, decision format, branch naming)

## Commits

1. `bf5feb9` Initial scaffold (57 files, 4491 lines)
2. `7037679` Pre-investigation pipeline with static analysis
3. `128ae42` Edoc network integration, live container access, Playwright

## Layer status

### FastAPI backend (~80%)

Done:
- [x] App setup, template routing, static files
- [x] Pipeline CRUD endpoints (list, get, create, cancel, retry)
- [x] Decision endpoints (list pending, get round, submit answers)
- [x] Worker endpoints (list, get, kill)
- [x] Internal IPC endpoints (phase-started, decisions-emitted, phase-completed, phase-failed, progress)
- [x] Internal API key auth middleware
- [x] Pipeline create dispatching investigate via Celery
- [x] Pipeline retry dispatching current phase via Celery
- [x] Answer submission writing answer files and triggering next worker
- [x] Phase-completed auto-dispatching next phase
- [x] Phase-failed auto-retry logic

Not wired:
- [x] Asana custom field sync (pylon_status, pylon_pr) on phase transitions
- [ ] Notification sends (Slack) on decisions-emitted, phase-failed
- [ ] Progress updates stored in Redis for fast polling

### SQLAlchemy models (100%)

- [x] Ticket, Pipeline, PhaseRun, DecisionRound, Decision, Answer, WorkerSession
- [x] All indexes and constraints
- [x] Relationships and back-references

### Pydantic schemas (100%)

- [x] All request/response types
- [x] Internal IPC schemas

### Celery tasks (~70%)

Done:
- [x] Celery app config with Redis broker
- [x] Beat schedule (poll-asana, detect-stale-workers, overnight-batch)
- [x] run_phase task structure with retry/timeout
- [x] Asana client (get tasks, update, comment, move section)
- [x] run_phase calling internal API on phase-started/completion/failure/decisions
- [x] poll_asana creating Ticket + Pipeline rows, deduplicating by asana_gid, dispatching investigate

Not wired:
- [x] overnight_batch querying queued pipelines and dispatching via chord
- [x] notify_batch_complete sending Slack webhook summary
- [x] Stale worker detection querying DB
- [x] Worktree cleanup for old pipelines

### Worker harness (~50%)

Done:
- [x] spawn_worker with env vars and subprocess
- [x] kill_worker with SIGTERM/SIGKILL grace period
- [x] Account rotation (naive round-robin)
- [x] IPC file read/write (config, status, result, decisions, answers)

Not wired:
- [x] Worktree creation (git worktree add) and branch creation
- [x] Account rotation checking DB for active sessions
- [x] Worker monitoring loop (health checks every 30s)
- [x] Decision file detection triggering API call

### Pre-investigation (~80%)

Done:
- [x] ctags symbol extraction
- [x] ripgrep keyword search
- [x] tree-sitter PHP class hierarchy
- [x] tree-sitter PHP model extraction (table, fillable, relationships, casts)
- [x] Route extraction (static regex + live artisan)
- [x] PHPStan (local + container)
- [x] Orchestrator running all analyzers in parallel
- [x] CLI entry point (check-tools, pre-investigate)
- [x] Auto-detect running containers, prefer live data

Not done:
- [ ] Test against real edoc repos (only tested with fake PHP fixtures)
- [ ] Tune keyword extraction from ticket context

### Live container access (~70%)

Done:
- [x] docker exec wrapper (artisan route:list, model:show, phpstan, tests)
- [x] Container running detection
- [x] Mailpit API client (list, search, get, delete messages)
- [x] Playwright browser harness (login, navigate, click, assert, screenshot)
- [x] Dockerfile.worker with Chromium + Docker CLI

Not done:
- [ ] Browser test step generation from implementation plan
- [ ] Screenshot storage and dashboard display
- [ ] Mailpit integration in test phase
- [ ] mkcert CA trust inside worker container

### HTMX frontend (~20%)

Done:
- [x] Base layout (nav, dark theme, Tailwind CDN, Alpine.js, HTMX)
- [x] Page shells (board, decisions, ticket detail, activity)
- [x] HTMX polling wired (board 10s, badge 30s)

Not done:
- [x] Board partial rendering pipeline cards in columns
- [x] Decision card partial with radio buttons and submit
- [x] Ticket detail partial with phase progress and history
- [ ] Activity feed partial
- [x] Badge partial showing pending decision count
- [ ] SSE for real-time updates (upgrade from polling)

### Tests (~25%)

Done:
- [x] Async test fixtures (DB, client)
- [x] Test factories (ticket, pipeline, phase_run, decision_round, decision)
- [x] Pipeline API tests (list, create, filter)
- [x] Decision API tests (submit answers)
- [x] IPC unit tests (read/write config, answers, result, round files)
- [x] Analyzer tests (tree-sitter classes/models, routes, pre-investigation)

Not done:
- [ ] Internal API tests
- [ ] Celery task tests (mocked subprocess)
- [ ] Worker harness tests
- [ ] Browser harness tests
- [ ] Integration test: full pipeline loop with mock Claude

### Database (~100%)

Done:
- [x] Alembic configured for async
- [x] Migration template
- [x] Initial migration (0001) with all 7 tables, indexes, constraints
- [x] Docker entrypoint runs migrations on api startup (RUN_MIGRATIONS env flag)
- [x] Seed data script with sample ticket, pipeline, decisions, worker session

### Docker (~90%)

Done:
- [x] Dockerfile (API/beat/flower)
- [x] Dockerfile.worker (+ Chromium, Docker CLI, Playwright)
- [x] docker-compose.yml with edoc network, repo volume mount, Docker socket
- [x] Health checks on Postgres and Redis

Not done:
- [ ] mkcert CA certificate in worker image for *.test HTTPS
- [ ] Production compose variant (if ever needed)
