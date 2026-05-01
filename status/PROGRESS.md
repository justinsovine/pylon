# Build Progress

Last updated: 2026-04-30

## Commits

1. `bf5feb9` Initial scaffold (57 files, 4491 lines)
2. `7037679` Pre-investigation pipeline with static analysis
3. `128ae42` Edoc network integration, live container access, Playwright

## Layer status

### FastAPI backend (~60%)

Done:
- [x] App setup, template routing, static files
- [x] Pipeline CRUD endpoints (list, get, create, cancel, retry)
- [x] Decision endpoints (list pending, get round, submit answers)
- [x] Worker endpoints (list, get, kill)
- [x] Internal IPC endpoints (phase-started, decisions-emitted, phase-completed, phase-failed, progress)
- [x] Internal API key auth middleware

Not wired:
- [ ] Pipeline create dispatching investigate via Celery
- [ ] Pipeline retry dispatching current phase via Celery
- [ ] Answer submission writing answer files and triggering next worker
- [ ] Phase-completed auto-dispatching next phase
- [ ] Phase-failed auto-retry logic
- [ ] Notification sends (Slack) on decisions-emitted, phase-failed
- [ ] Progress updates stored in Redis for fast polling
- [ ] Slug generation from Asana title

### SQLAlchemy models (100%)

- [x] Ticket, Pipeline, PhaseRun, DecisionRound, Decision, Answer, WorkerSession
- [x] All indexes and constraints
- [x] Relationships and back-references

### Pydantic schemas (100%)

- [x] All request/response types
- [x] Internal IPC schemas

### Celery tasks (~30%)

Done:
- [x] Celery app config with Redis broker
- [x] Beat schedule (poll-asana, detect-stale-workers, overnight-batch)
- [x] run_phase task structure with retry/timeout
- [x] Asana client (get tasks, update, comment, move section)

Not wired:
- [ ] run_phase calling internal API on completion/failure/decisions
- [ ] overnight_batch polling Asana and creating pipelines
- [ ] notify_batch_complete sending Slack messages
- [ ] Asana poller creating tickets and pipelines in DB
- [ ] Stale worker detection querying DB
- [ ] Worktree cleanup for old pipelines

### Worker harness (~50%)

Done:
- [x] spawn_worker with env vars and subprocess
- [x] kill_worker with SIGTERM/SIGKILL grace period
- [x] Account rotation (naive round-robin)
- [x] IPC file read/write (config, status, result, decisions, answers)

Not wired:
- [ ] Account rotation checking DB for active sessions
- [ ] Worktree creation (git worktree add)
- [ ] Branch creation (git checkout -b)
- [ ] Worker monitoring loop (health checks every 30s)
- [ ] Decision file detection triggering API call

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
- [ ] Board partial rendering pipeline cards in columns
- [ ] Decision card partial with radio buttons and submit
- [ ] Ticket detail partial with phase progress and history
- [ ] Activity feed partial
- [ ] Badge partial showing pending decision count
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

### Database (~10%)

Done:
- [x] Alembic configured for async
- [x] Migration template

Not done:
- [ ] Generate and run initial migration
- [ ] Seed data for development

### Docker (~90%)

Done:
- [x] Dockerfile (API/beat/flower)
- [x] Dockerfile.worker (+ Chromium, Docker CLI, Playwright)
- [x] docker-compose.yml with edoc network, repo volume mount, Docker socket
- [x] Health checks on Postgres and Redis

Not done:
- [ ] mkcert CA certificate in worker image for *.test HTTPS
- [ ] Production compose variant (if ever needed)
