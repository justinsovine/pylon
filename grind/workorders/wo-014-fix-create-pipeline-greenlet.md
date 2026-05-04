# WO-014: Fix MissingGreenlet in create_pipeline

## Scope
Add selectinload(Pipeline.ticket) to create_pipeline endpoint so response serialization can access ticket relationship. Small.

## Files to read
- src/pylon/api/pipelines.py (lines 53-81: create_pipeline endpoint)
- tests/test_api/test_pipelines.py (test_create_pipeline: currently failing)

## Key context

List and get endpoints already use selectinload:
```python
# pipelines.py line 27 (list)
query = select(Pipeline).join(Ticket).options(selectinload(Pipeline.ticket))

# pipelines.py line 46 (get)
.options(selectinload(Pipeline.ticket))
```

Create endpoint returns pipeline after `db.refresh(pipeline)` but ticket relationship not loaded:
```python
# pipelines.py lines 76-81
await db.commit()
await db.refresh(pipeline)

run_phase.delay(str(pipeline.id), "investigate")

return pipeline  # <-- PipelineOut needs .ticket, but not loaded
```

PipelineOut response model includes ticket field, triggers lazy load outside async context.

## Changes
- [ ] src/pylon/api/pipelines.py: Add `selectinload(Pipeline.ticket)` to refresh or re-query after commit

## Proposed implementation

Replace the refresh with a query that includes selectinload:
```python
await db.commit()

result = await db.execute(
    select(Pipeline)
    .where(Pipeline.id == pipeline.id)
    .options(selectinload(Pipeline.ticket))
)
pipeline = result.scalar_one()

run_phase.delay(str(pipeline.id), "investigate")

return pipeline
```

## Decisions
None. Straightforward bug fix matching existing pattern.

## Tests
Requirements: async DB
Run: `pytest tests/test_api/test_pipelines.py::test_create_pipeline -v`
- [ ] test_create_pipeline passes (currently failing with MissingGreenlet)

## Commit
```
fix(api): add selectinload to create_pipeline endpoint

Pipeline.ticket relationship not loaded after refresh, causing
MissingGreenlet during PipelineOut response serialization.
```

## Dependencies
blocked_by: none
blocks: wo-011

## After commit
- Verify 4 failed -> 3 failed (tree_sitter failures remain, unrelated)
