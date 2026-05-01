# Project Context

Information about the team, repos, and environment that isn't captured
in code or design docs. Derived from conversation on 2026-04-30.

## Team

Three active developers at EdocServiceInc:

| Name | Role | Primary repos | Notes |
|------|------|--------------|-------|
| Justin Sovine | Lead / this project's author | All three, heaviest on esign | Built /feature skill, security PoC, this project |
| Tanya (Landreth) | Developer | scriptus-web (80% of commits), onboard | 1,057 commits to scriptus-web in 2025 |
| Michael Messerli | Developer | onboard, scriptus-web | 185 commits to onboard in 2025 |

Lighter contributors: T.A. Landreth, Terry Hill. Bots: dependabot, copilot-swe-agent.

## Repos

Three Laravel 9 / PHP 8.1 apps under EdocServiceInc GitHub org:

| Repo | PHP files | Controllers | Tests | 2025 commits | Has CLAUDE.md |
|------|-----------|-------------|-------|-------------|---------------|
| esign | 365 | 36 | 8 | 72 | No |
| onboard | 264 | 33 | 33 | 698 | Yes |
| scriptus-web | 222 | 34 | 16 | 1,307 | No |

All use: Laravel Sail (Docker), Tailwind, Livewire, Alpine.js.
All connect via shared `edoc` Docker network through local-proxy (nginx).

### Onboard specifics (most mature for Pylon)
- Multi-tenant: Bureau/Client structure. Clients have Customers who onboard Workers.
- 6 role types: Super Admin, EDoc Admin, Admin, Customer Admin, Group Admin, Worker
- 39 Livewire components
- 17 route files (well-organized)
- Integrations: eSign, CPO, Twilio, Postmark, Scriptus/ePoster
- PHPStan level 3 with baseline
- Git branches: dev -> Sandbox, production -> Production, master is main

### Security findings (2026-04-08)
Justin authored a security PoC (`~/code/edoc/notes/security-poc-high-priority.sh`)
documenting 5 high-priority unauthenticated access issues in onboard:
1. Client URL enumeration (no auth on /api/get-url/client/{id})
2. Customer URL enumeration (no auth on /api/get-url/customer/{id})
3. API login with commented-out auth check, no rate limiting
4. Postmark webhook authenticating against user table
5. Offer letter accept/decline with no auth middleware

These should be fixed before Pylon automates work against these APIs.

## Infrastructure

- Asana for ticket management
- GitHub (EdocServiceInc org) for repos
- Local development via Docker + Laravel Sail
- local-proxy repo: shared nginx reverse proxy for *.test domains with mkcert HTTPS
- 3 Claude Code accounts available for workers

## Origin story

This project started from analyzing a Reddit post about Claude Code workflows
(r/ClaudeCode, "Six layers that turned my Claude Code into a 24/7 dev team").
Justin had already built the /feature skill for structured development phases.
The conversation evolved:

1. Could /feature be automated against Asana tickets?
2. Yes, but refine/critique phases need human input
3. What if humans answer in batches via a dashboard instead of terminal?
4. That's a product: Pylon
5. Add live container access for pre-investigation and browser testing
6. Add pre-investigation static analysis to reduce token costs

Key realization: the Reddit post optimized for autonomous agents. Pylon
optimizes for human-in-the-loop with agent leverage. Humans decide, agents
execute. That's the differentiator.

## Relationship to OpenClaw

Evaluated whether Pylon duplicates OpenClaw (open-source personal AI agent,
68k+ GitHub stars). Conclusion: different tools. OpenClaw is a general-purpose
agent gateway (chat apps -> LLM -> tools). Pylon is a domain-specific
development pipeline with structured phases and decision batching. They
complement, don't compete. OpenClaw runs on the P40 for personal assistant
tasks. Pylon runs separately for team development workflow.
