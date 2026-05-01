# Decisions Made

Decisions that have been made and shouldn't be re-litigated unless
context changes significantly. Each entry records what was decided,
why, and what alternatives were rejected.

## Architecture

### /pylon is a clean fork of /feature, not a wrapper
- Date: 2026-04-30
- Decision: /pylon has its own skill phases, its own skill directory, its own phase files. It was inspired by /feature but shares no code.
- Why: /feature is terminal-first interactive. /pylon is dashboard-first structured-output. Sharing code means every phase has conditional branching (terminal mode vs pylon mode). Clean fork is simpler, lets both evolve independently.
- Rejected: Shared engine with PYLON_WORKER env var toggling behavior.

### Phase-per-invocation, not long-lived sessions
- Date: 2026-04-30
- Decision: Each phase runs as a separate `claude -p` invocation. No persistent Claude Code sessions.
- Why: Simpler failure recovery (crash = re-run phase). Notes carry state between invocations. No idle sessions burning API credits while waiting for human decisions.
- Rejected: Long-lived sessions with file-based IPC (too much process management complexity).

### Decision batching in rounds
- Date: 2026-04-30
- Decision: Refine and critique phases emit all independent decisions in one round. Dependent decisions come in subsequent rounds.
- Why: Better dashboard UX (answer 3 decisions at once, not 3 separate pings). Fewer worker invocations. Most features need 2 rounds max.
- Rejected: One-at-a-time Q&A (terminal model, bad for async). Full autonomy with agent deciding (loses human judgment).

### Human stays in the decision loop
- Date: 2026-04-30
- Decision: No fully autonomous mode. Every ticket goes through human refine + critique. Agent handles investigation, planning, implementation, testing, PR.
- Why: Original design had --unattended flag where agent makes decisions based on guidelines. Revised: agents investigate and present decisions, humans decide in batches. Better quality, maintains accountability.
- Rejected: --unattended flag with autonomous decision-making.

## Stack

### Python / FastAPI for backend
- Date: 2026-04-30
- Decision: Python, not PHP or Node.
- Why: Best subprocess management (asyncio.create_subprocess). This is an orchestrator, not a web app. PHP's process model fights long-running workers. Team doesn't need to maintain Pylon like the Laravel repos.
- Rejected: PHP/Laravel (team knows it but wrong tool), Node/Fastify (subprocess management less mature).

### Celery + Redis for queue
- Date: 2026-04-30
- Decision: Celery with Redis broker.
- Why: User wants it. Retry with backoff, timeouts, Flower dashboard, chord/chain primitives for batch operations.
- Rejected: Postgres SKIP LOCKED (simpler but user prefers Celery). Plain subprocess with concurrent.futures.

### HTMX + Jinja for frontend v1
- Date: 2026-04-30
- Decision: Server-rendered HTML with HTMX for dynamic updates. No React.
- Why: One app, one deploy, no build step. 3 users, internal tool. Decision cards and status lists are trivially expressible in HTMX. Team already knows Tailwind + Alpine.js from Laravel projects.
- Rejected: React (overkill for v1), Next.js (two backends problem), Livewire (requires Laravel backend).

### PostgreSQL
- Date: 2026-04-30
- Decision: Postgres, not SQLite.
- Why: JSONB for decision option payloads. LISTEN/NOTIFY for real-time events. Concurrent writes from multiple workers.
- Rejected: SQLite (concurrent write contention, no pub/sub).

## Workflow

### Daily rhythm: overnight investigate, morning decisions, afternoon PRs
- Date: 2026-04-30
- Decision: Agents investigate 4 tickets per dev overnight. Devs answer refine decisions in morning. Agents plan, devs critique, agents implement. PRs by afternoon.
- Why: Human touches each ticket twice (refine + critique). Agent does everything between. Maximizes dev throughput without sacrificing decision quality.

### Pylon joins the edoc Docker network
- Date: 2026-04-30
- Decision: Pylon containers join the shared `edoc` Docker network.
- Why: Direct access to app containers for live pre-investigation (artisan, phpstan), browser testing (Playwright against dev.onboard.test), and email verification (Mailpit API). Discovered from reviewing local-proxy setup.

## Naming

### Project name: Pylon
- Date: 2026-04-30
- Decision: Pylon. Not a placeholder.
