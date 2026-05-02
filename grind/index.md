# Grind Index

Project: Pylon
Created: 2026-05-02
Last retune: 2026-05-02
Branch: main
Source: BUILDPLAN/ docs + status/backlog/critical-path.md + codebase investigation

## Decisions Log
- D1: Board columns -- Option A, 6 columns matching BUILDPLAN spec
- D2: Slack format -- Option C, plain text + mrkdwn
- D3: Dashboard auth -- Option B, no auth for v1, assignee via dropdown
- D4: Integration test mock -- Option A, fake subprocess emitting IPC files

## In Progress
<!-- next writes the current workorder here -->

## Up Next
- [wo-003](workorders/wo-003-badge-ticket-detail.md) | blocked_by: none | est: small
- [wo-004](workorders/wo-004-activity-feed.md) | blocked_by: none | est: small
- [wo-005](workorders/wo-005-slack-notifications.md) | blocked_by: none | est: small
- [wo-006](workorders/wo-006-redis-progress.md) | blocked_by: none | est: small
- [wo-008](workorders/wo-008-internal-api-tests.md) | blocked_by: none | est: medium
- [wo-009](workorders/wo-009-celery-task-tests.md) | blocked_by: none | est: medium
- [wo-010](workorders/wo-010-harness-tests.md) | blocked_by: none | est: medium
- [wo-011](workorders/wo-011-integration-test.md) | blocked_by: wo-008, wo-009, wo-010 | est: large
- [wo-012](workorders/wo-012-skill-test-protocol.md) | blocked_by: none | est: small

## Done
- [wo-013](workorders/done/wo-013-jinja2-template-cache-bug.md) | commit: a155fdd | completed: 2026-05-02
- [wo-002](workorders/done/wo-002-decision-partial.md) | commit: 68c5820 | completed: 2026-05-02
- [wo-001](workorders/done/wo-001-board-partial.md) | commit: 1f426a6 | completed: 2026-05-02

## Inbox
<!-- next adds discoveries here for retune to process -->
