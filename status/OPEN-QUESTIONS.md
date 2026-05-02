# Open Questions

Items needing a decision before they can be built. Each entry describes the
question, the options considered so far, and what's blocking the decision.

## Auth model for the dashboard

**Question:** How do 3 users authenticate to the Pylon dashboard?

Options:
1. **Hardcoded users in config** -- email + bcrypt password in settings. Simplest. No external deps.
2. **OAuth via Google Workspace** -- if EdocServiceInc uses Google. SSO convenience.
3. **Clerk** -- already used in esign. Shared auth across tools.
4. **No auth** -- internal network only, trust the network. Fastest to ship.

Leaning: Hardcoded for v1. Upgrade later if needed.
Blocked by: Nothing. Just needs a decision.

## Product vs internal tool

**Question:** Does Pylon stay an internal tool for EdocServiceInc or become a product?

Implications:
- Internal: hardcoded for 3 Laravel repos, 3 devs, Asana. No need for onboarding, billing, multi-tenancy.
- Product: needs to be repo-agnostic, PM-tool-agnostic, support arbitrary team sizes. Completely different scope.

Leaning: Build internal first. Evaluate product viability after 3 months of use.
Blocked by: Premature to decide. Ship internal, gather data.

## Mobile strategy

**Question:** How do devs answer decisions on their phone?

Options:
1. **Just responsive web** -- Tailwind handles it. Decision cards stack vertically.
2. **PWA** -- add manifest, service worker. Install to home screen.
3. **Native app** -- massive scope increase. Not justified.

Leaning: Responsive web first. Add PWA manifest if devs actually use it on mobile.
Blocked by: Nothing. Responsive is default. PWA is ~2 hours of work.

## Cross-repo features

**Question:** How does Pylon handle a ticket that touches both onboard and esign (e.g., onboard calls esign API)?

Options:
1. **One pipeline, one repo** -- ticket targets primary repo. Cross-repo implications noted in investigation but not automated.
2. **Linked pipelines** -- ticket creates pipelines in both repos. Coordinate phase merges them.
3. **Multi-repo worktree** -- single pipeline checks out both repos.

Leaning: Option 1 for v1. Cross-repo is rare and complex.
Blocked by: Nothing. Build for single-repo first.

## Test credential management

**Question:** How does Playwright get login credentials for each app's local dev environment?

Options:
1. **Env vars** -- TEST_CREDENTIALS_ONBOARD_EMAIL etc. Currently in .env.example.
2. **Seeder convention** -- each app seeds a known test user. Pylon knows the convention.
3. **Shared config file** -- credentials.json (gitignored).

Leaning: Env vars + seeder convention. Each app's UserSeeder creates a known dev account.
Blocked by: Need to verify each app's seeder has a predictable test user.

## P40 server timeline

**Question:** When is the local AI server being built, and does Pylon run on it?

Context: Budget build (~$530-580) with Tesla P40 for OpenClaw. Pylon doesn't need GPU (Claude API is remote) but benefits from always-on infra.

Options:
1. **Pylon on P40 box** -- runs alongside OpenClaw. GPU for local LLM, CPU for Pylon.
2. **Pylon on VPS** -- $7/mo Hetzner. Always on, no local dependency.
3. **Pylon on workstation** -- simplest but machine must be on for overnight runs.

Leaning: P40 box when built. Workstation until then.
Blocked by: P40 hardware purchase timeline.

## Prompt engineering for structured output

**Status: Partially resolved.** Skill phase files written (2026-05-02). IPC contract defined in SKILL.md. Still needs manual testing with `claude -p` to validate Claude actually follows the contract reliably.

Remaining risks:
- Claude may produce malformed JSON or write to wrong paths
- Decision `depends_on` ordering may confuse the model
- Long phases (implement, 45min) may lose context of the IPC contract after compaction
- Need to test whether `--output-format text` interferes with file-writing tool calls

Blocked by: Manual testing against real ticket.

## Wiring gaps found during skill authoring (2026-05-02)

Building the /pylon skill files exposed these mismatches between the skill contract and the harness code:

### 1. ~~Ticket context never reaches the skill~~ RESOLVED

Fixed 2026-05-02: `_run_phase` now calls `write_ticket_context(notes_path, ticket_data)` which writes `ticket.json` with title, description, assignee, repo, priority, asana_gid. `_get_pipeline_info` expanded to return full ticket fields.

### 2. ~~`asana_gid` and `answers_file` never passed to `spawn_worker`~~ RESOLVED

Fixed 2026-05-02: Chose option B. Removed `asana_gid` and `answers_file` params from `spawn_worker`. Dropped `--asana` and `--decisions` flags from prompt. Skill reads ticket context from `ticket.json` (fix #1) and finds answers by scanning `.pylon/decisions/round-*-answers.json`.

### 3. ~~Decision options format mismatch~~ RESOLVED

Fixed 2026-05-02: Standardized on structured format (`key/label/tradeoff`). Seed data updated to match `DecisionOption` schema. Dashboard renders structured format.

### 4. `status.json` is write-only

Skill writes `.pylon/status.json` for progress updates. Harness never reads it. The `/progress` internal endpoint exists but nothing calls it. The monitor loop only watches for decision files.

**Fix options:**
- A) Add status.json polling to `monitor_decisions`. Post to `/progress` endpoint. Store in Redis for dashboard polling.
- B) Drop status.json from the skill contract. Progress is implicit from phase transitions.

Leaning: Option A eventually, but not blocking. Dashboard can show phase-level status (from DB) without sub-phase granularity.

### 5. ~~Branch naming: per-pipeline or per-phase?~~ RESOLVED

Fixed 2026-05-02: Seed data branch_name changed from `pylon/{slug}/investigate` to `pylon/{slug}`. All phases commit to same branch. `_poll_asana` already used correct `pylon/{slug}` format.

### 6. ~~`--output-format text` may suppress tool output~~ RESOLVED

Tested 2026-05-02: `claude -p --output-format text` executes tool calls normally (Write tool creates files as expected). The flag only controls stdout format, not tool execution. No changes needed.
