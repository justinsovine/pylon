# Pylon -- Relationship to /feature

## Two separate skills

/feature and /pylon are independent skills. /pylon was inspired by /feature's phase structure but is a clean fork with its own implementation.

```
/feature                              /pylon
  Terminal-first                        Dashboard-first
  Interactive Q&A                       Structured decision emission
  Single-player                         Multi-user (3 devs)
  One ticket at a time                  Batch processing
  Human drives the session              Orchestrator drives workers
  Notes carry state                     Notes + Postgres + .pylon/ carry state
  Phases: investigate, refine,          Phases: forked from /feature, 
    plan, critique, coordinate,           evolved independently
    implement, test, pr, review, 
    announce
```

## What /pylon takes from /feature

- Phase progression concept (investigate before plan, plan before implement)
- Notes directory convention (structured markdown artifacts per feature)
- Investigation depth (trace full data flow, not just grep for files)
- Plan structure (staged, with commit messages, deployment notes)
- Re-entry model (run earlier phases again on same feature)

## What /pylon changes

- Decision points are structured JSON, not conversational Q&A
- Phases are designed for batch emission (round-based decisions)
- No interactive terminal mode. Every phase either runs to completion or emits decisions and exits.
- Progress reporting is built in (status.json, API calls)
- Phases may be merged or split differently as Pylon evolves
- No coordinate phase (Pylon handles multi-ticket orchestration at the system level, not the skill level)
- No review/announce phases (PR review is human, announcements are handled by dashboard/Slack integration)

## Evolution

/feature continues to evolve for interactive terminal use. /pylon evolves for orchestrated dashboard use. They may diverge significantly over time. That's fine. They solve different problems.

If a /feature improvement is useful for /pylon, port it manually. No shared dependency.
