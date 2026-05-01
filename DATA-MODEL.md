# Pylon -- Data Model

## Entity relationship

```
Ticket (from Asana)
  │
  └── Pipeline (1:1 with ticket)
        │
        ├── Phase Runs (ordered, one per phase attempted)
        │     │
        │     └── Decision Rounds (ordered within a phase)
        │           │
        │           └── Decisions (multiple per round)
        │                 │
        │                 └── Answer (0 or 1 per decision)
        │
        └── Worker Sessions (1 per phase invocation, including retries)
```

## Tables

### tickets

Source of truth stays in Asana. This table caches what Pylon needs.

```sql
CREATE TABLE tickets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asana_gid       TEXT UNIQUE NOT NULL,
    slug            TEXT UNIQUE NOT NULL,        -- kebab-case, used for notes dir + branch name
    title           TEXT NOT NULL,
    description     TEXT,
    assignee        TEXT,                        -- dev name: justin, tanya, michael
    repo            TEXT NOT NULL,               -- esign, onboard, scriptus-web
    priority        TEXT,                        -- from Asana custom field
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### pipelines

One pipeline per ticket. Tracks overall state.

```sql
CREATE TABLE pipelines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID UNIQUE NOT NULL REFERENCES tickets(id),
    status          TEXT NOT NULL DEFAULT 'queued',
    -- queued: waiting to start
    -- investigating, refining, planning, critiquing, implementing, testing, pr_creating
    -- awaiting_decisions: parked, waiting for human input
    -- completed: PR opened
    -- failed: unrecoverable error
    -- cancelled: manually stopped
    current_phase   TEXT,                        -- investigate, refine, plan, critique, implement, test, pr
    branch_name     TEXT,                        -- feature/ticket-slug
    notes_path      TEXT,                        -- relative path to notes directory
    pr_url          TEXT,                        -- set when PR is created
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### phase_runs

Each time a phase executes (including retries and re-entries).

```sql
CREATE TABLE phase_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id     UUID NOT NULL REFERENCES pipelines(id),
    phase           TEXT NOT NULL,               -- investigate, refine, plan, critique, implement, test, pr
    pass_number     INT NOT NULL DEFAULT 1,      -- re-entry tracking (pass 1, pass 2, etc.)
    status          TEXT NOT NULL DEFAULT 'pending',
    -- pending, running, awaiting_decisions, completed, failed, skipped
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    worker_id       UUID REFERENCES worker_sessions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### decision_rounds

Groups of decisions emitted together within a phase. Round 2 depends on round 1 answers.

```sql
CREATE TABLE decision_rounds (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phase_run_id    UUID NOT NULL REFERENCES phase_runs(id),
    round_number    INT NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'pending',
    -- pending: not yet emitted by worker
    -- awaiting: decisions surfaced, waiting for human answers
    -- answered: all decisions in this round answered
    -- applied: answers fed back to worker, next round (or phase completion) started
    emitted_at      TIMESTAMPTZ,
    answered_at     TIMESTAMPTZ,
    applied_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### decisions

Individual decision points within a round.

```sql
CREATE TABLE decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    round_id            UUID NOT NULL REFERENCES decision_rounds(id),
    decision_key        TEXT NOT NULL,            -- d001, d002, etc. (stable within a phase run)
    question            TEXT NOT NULL,
    context             TEXT,                     -- investigation findings relevant to this decision
    options             JSONB NOT NULL,           -- array of {key, label, tradeoff}
    recommendation      TEXT,                     -- key of recommended option
    recommendation_why  TEXT,
    depends_on          TEXT,                     -- decision_key of dependency (null if independent)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(round_id, decision_key)
);
```

### answers

Human responses to decisions.

```sql
CREATE TABLE answers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     UUID UNIQUE NOT NULL REFERENCES decisions(id),
    choice          TEXT NOT NULL,               -- option key (A, B, C) or "freeform"
    note            TEXT,                        -- human's additional context
    answered_by     TEXT NOT NULL,               -- dev name
    source          TEXT NOT NULL DEFAULT 'dashboard',  -- dashboard, terminal, auto
    answered_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### worker_sessions

Tracks each Claude Code process invocation.

```sql
CREATE TABLE worker_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id     UUID NOT NULL REFERENCES pipelines(id),
    phase           TEXT NOT NULL,
    pid             INT,                         -- OS process ID
    account         TEXT,                        -- which Claude account (worker-a, worker-b, etc.)
    status          TEXT NOT NULL DEFAULT 'starting',
    -- starting, running, waiting, completed, failed, timed_out, killed
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    timeout_seconds INT DEFAULT 1800,            -- 30 min default
    exit_code       INT,
    error_output    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Indexes

```sql
CREATE INDEX idx_pipelines_status ON pipelines(status);
CREATE INDEX idx_pipelines_assignee ON pipelines(ticket_id);  -- join to tickets.assignee
CREATE INDEX idx_phase_runs_pipeline ON phase_runs(pipeline_id, phase);
CREATE INDEX idx_decisions_round ON decisions(round_id);
CREATE INDEX idx_answers_decision ON answers(decision_id);
CREATE INDEX idx_worker_sessions_status ON worker_sessions(status);
CREATE INDEX idx_tickets_assignee ON tickets(assignee);
CREATE INDEX idx_tickets_repo ON tickets(repo);
```

## Key queries

```sql
-- Dashboard: all pending decisions for a user
SELECT d.*, dr.round_number, p.current_phase, t.title, t.slug
FROM decisions d
JOIN decision_rounds dr ON d.round_id = dr.id
JOIN phase_runs pr ON dr.phase_run_id = pr.id
JOIN pipelines p ON pr.pipeline_id = p.id
JOIN tickets t ON p.ticket_id = t.id
LEFT JOIN answers a ON d.id = a.decision_id
WHERE t.assignee = 'justin'
  AND a.id IS NULL
  AND dr.status = 'awaiting'
ORDER BY dr.emitted_at;

-- Pipeline status board
SELECT t.slug, t.title, t.assignee, t.repo,
       p.status, p.current_phase, p.pr_url,
       (SELECT count(*) FROM decisions d
        JOIN decision_rounds dr ON d.round_id = dr.id
        JOIN phase_runs pr2 ON dr.phase_run_id = pr2.id
        WHERE pr2.pipeline_id = p.id
        AND d.id NOT IN (SELECT decision_id FROM answers)
       ) as pending_decisions
FROM pipelines p
JOIN tickets t ON p.ticket_id = t.id
ORDER BY p.updated_at DESC;

-- Worker health
SELECT ws.*, t.slug
FROM worker_sessions ws
JOIN pipelines p ON ws.pipeline_id = p.id
JOIN tickets t ON p.ticket_id = t.id
WHERE ws.status IN ('starting', 'running', 'waiting')
ORDER BY ws.started_at;
```

## Notes on the model

Decision payloads use JSONB for options because the structure varies (some decisions have 2 options, some have 5, some have nested context). Everything else is normalized.

The pass_number on phase_runs supports /feature's re-entry model. If investigate runs twice, that's two phase_run rows with pass_number 1 and 2.

Worker sessions are separate from phase runs because a phase might need multiple worker invocations (round 1 decisions answered, spawn new worker for round 2). One phase_run can have multiple worker_sessions.
