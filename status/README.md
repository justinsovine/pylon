# Pylon Project Status

This directory tracks project state that lives between conversations.
Code and design docs capture what's built and planned. This directory
captures what's in progress, what's decided, and what's still open.

## Structure

```
status/
  README.md              # this file
  PROGRESS.md            # what's built, what's wired, what's TODO
  DECISIONS.md           # decisions made and why (prevents re-litigating)
  OPEN-QUESTIONS.md      # undecided items needing human input
  CONTEXT.md             # team, repo, and project context not in code
  backlog/               # future work, grouped by area
    critical-path.md     # must-do for end-to-end loop
    important.md         # not blocking but needed
    polish.md            # nice-to-have, quality-of-life
```

Update these files as work progresses. When a decision is made, move it
from OPEN-QUESTIONS.md to DECISIONS.md. When a TODO is done, check it off
in PROGRESS.md and the relevant backlog file.
