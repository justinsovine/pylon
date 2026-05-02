# Discovery: Pre-existing test failures

Found during: wo-006
Affects: wo-008, wo-009, wo-011 (test-related workorders)
Details: 4 tests fail independent of wo-006 changes. test_create_pipeline has a FastAPI validation error. Three tree_sitter analyzer tests fail (test_tree_sitter_extract_classes, test_tree_sitter_extract_models, test_tree_sitter_format_models). These should be fixed before wo-011 integration test work.
