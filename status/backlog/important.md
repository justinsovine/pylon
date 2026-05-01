# Important

Not blocking the first loop but needed for real daily use.

## Pre-investigation validation

- [ ] Test analyzers against real edoc repos (onboard, esign, scriptus-web)
- [ ] Tune keyword extraction from Asana ticket descriptions
- [ ] Verify tree-sitter PHP handles all patterns in edoc codebase

## Live container access

- [ ] mkcert CA trust inside worker container for *.test HTTPS
- [ ] Browser test step generation from implementation plan
- [ ] Screenshot storage and dashboard display
- [ ] Mailpit integration in test phase (verify emails sent by features)

## Dashboard completeness

- [ ] Ticket detail partial with phase progress timeline and history
- [ ] Activity feed partial (recent events across all pipelines)
- [ ] SSE upgrade from polling for real-time updates

## Testing

- [ ] Internal API endpoint tests
- [ ] Celery task tests (mocked subprocess)
- [ ] Worker harness tests
- [ ] Browser harness tests
- [ ] Integration test: full pipeline loop with mock Claude responses

## Progress tracking

- [ ] Redis-backed progress updates for fast polling (not DB queries)
- [ ] Slug generation from Asana title for readable branch/directory names

## Auth

- [ ] Decide auth model (leaning hardcoded users in config for v1)
- [ ] Implement chosen auth on all dashboard routes

## Error handling

- [ ] Phase-failed auto-retry with exponential backoff
- [ ] Stale worker detection querying DB and killing zombies
- [ ] Worktree cleanup for completed/failed pipelines
