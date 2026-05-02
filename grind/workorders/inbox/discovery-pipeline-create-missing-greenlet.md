# Discovery: test_create_pipeline MissingGreenlet failure

Found during: wo-013
Affects: wo-008 (internal API tests), wo-011 (integration test)
Details: `test_create_pipeline` fails with `MissingGreenlet` on response serialization. Pipeline.ticket relationship accessed outside async context during Pydantic response validation. Likely needs `selectinload(Pipeline.ticket)` in the create endpoint or eager loading in the response model. Pre-existing, not caused by any recent workorder.
