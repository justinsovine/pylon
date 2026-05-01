# Pylon (working title)

## One-liner

Async feature development pipeline that runs Claude Code workers against Asana tickets and surfaces decision points in a web dashboard for human review.

## The problem

Three developers. Three Laravel repos. Tickets in Asana. Today, each dev manually investigates code, makes scope decisions, plans implementation, writes code, writes tests, opens PRs. Claude Code helps interactively but it's single-player, synchronous, and terminal-bound.

The /feature skill already structures this into phases (investigate, refine, plan, critique, implement, test, pr). But it requires a human sitting in a terminal for each phase of each ticket. The human's actual value is concentrated in two moments: making scope/approach decisions (refine) and vetting the plan (critique). Everything else is agent work.

## The idea

Decouple the human from the terminal. Let agents run phases autonomously. When they hit a decision point, park the work and surface the question in a dashboard. Human answers when ready -- between meetings, on their phone, over coffee. Agent resumes. PRs appear.

## Daily rhythm (target state)

```
Overnight    Agents investigate next batch of tickets (4 per dev)
Morning      Devs open dashboard, answer refine decisions (~5 min each)
             Agents plan all tickets
             Devs review plans, answer critique questions (~5 min each)
             Agents implement, test, open PRs
Afternoon    Devs review PRs, merge
```

Three devs, four tickets each, twelve PRs a day at peak. Realistic target: 4-6 good PRs/day across the team.

## Core concepts

### Pipeline

A ticket moves through phases in order. Each phase either runs to completion or parks at a decision point.

```
investigate -> refine -> plan -> critique -> implement -> test -> pr
                 ^          ^
                 |          |
            human input  human input
```

Phases without decision points (investigate, implement, test, pr) run unattended. Phases with decision points (refine, critique) park and wait.

### Decision point

A structured question surfaced by an agent when it needs human judgment. Contains:

- The question (what are we deciding?)
- Options with tradeoffs (what are the choices?)
- A recommendation (what does the agent think?)
- Context (what did the investigation find that's relevant?)

Human picks an option or writes a freeform response. Agent resumes with the answer.

### Worker

A Claude Code process running a single phase of a single ticket. Operates in its own git worktree. Reads from and writes to the shared notes directory. Communicates decision points and progress through the API.

### Notes

Structured markdown artifacts produced by each phase. Investigation findings, scope decisions, implementation plans, critique results. These are the persistent state of the pipeline -- a worker can crash and a new one picks up from the notes.

### Dashboard

Web UI showing:

- All active tickets and their current phase/status
- Pending decision points waiting for human input
- Decision history (what was decided, by whom, when)
- Pipeline progress (stages completed, estimated time)
- Links to PRs when ready

## What it is NOT

- Not a replacement for code review. Humans still review PRs.
- Not a project management tool. Asana stays the source of truth for tickets.
- Not a general-purpose agent framework. This is specifically for the /feature development workflow.
- Not autonomous. Every meaningful decision goes through a human. The agent handles the work between decisions.

## Who uses it

Initially: Justin, Tanya, Michael (EdocServiceInc dev team).
Three Laravel repos: esign, onboard, scriptus-web.
Asana as the ticket source.

## Open questions

- Name (pylon is a placeholder)
- How workers communicate with the API (file polling, HTTP, websocket?)
- How to handle worker failures and retries
- Auth model for the dashboard (tie to existing Clerk? standalone?)
- Mobile experience (PWA? native? just responsive web?)
- How /feature skill phases emit structured output vs terminal output
- Whether this becomes a product or stays an internal tool
