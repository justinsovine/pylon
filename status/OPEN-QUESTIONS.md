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

**Question:** How exactly do the /pylon skill phase instructions tell Claude to emit structured JSON decision files instead of conversational text?

This is the hardest unsolved problem. The skill markdown needs to instruct
Claude to:
- Analyze all decisions upfront (not one at a time)
- Map dependencies between decisions
- Write valid JSON to a specific file path
- Exit cleanly after emitting decisions

No prototype exists yet. Needs experimentation.
Blocked by: Need to write the /pylon skill phases and test them.
