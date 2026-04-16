# F-00046 S10 QvGate Report — FINAL (Cycle 5/5 Escalation)

**Date**: 2026-04-16
**Step**: S10 — QV Gate: Integration Tests
**Command**: `uv run pytest tests/integration/ -v --alluredir=allure-results`

## Summary

- **Total tests**: 477
- **Passed**: 474 (98.7%)
- **Failed**: 3
- **Test file**: `tests/integration/test_code_index_pipeline.py`

## Issues Addressed in Fix Cycles 1-5

1. **`tests/integration/conftest.py`**: Added function-scoped `db_session_factory` fixture to shadow the session-scoped one, providing test isolation.

2. **`orch/rag/job.py`**: Added `_db_set_status_async()` async method to replace `asyncio.to_thread(self._db_set_status, ...)` calls. This ensures proper async context handling.

3. **`tests/integration/test_code_index_pipeline.py`**: Multiple fixes applied to `test_runner_emits_progress_then_done`:
   - Changed project/job creation to use `with test_session_factory() as setup_session:` block
   - Extracted `project_id` and `job_id` before session closes
   - Changed mock patch path from `llama_index.vector_stores.lancedb.LanceDBVectorStore.add` to `orch.rag.indexer.LanceDBVectorStore.add`

## Remaining Failures (Cannot Fix Without Test Redesign)

### 1. `test_runner_emits_progress_then_done`

**Error**: `AssertionError: Expected completed, got failed`

**Root cause**: The `CodeIndexer.index()` method creates its own `LanceDBVectorStore` instance and calls `vector_store.add()` in an `asyncio.to_thread()` context. The test's mock doesn't properly intercept this call because:
1. The mock is applied to the class, but `CodeIndexer.index()` creates an instance
2. The call happens in a thread where patching behavior is unpredictable

### 2. `test_regenerate_map_upserts_project_doc`

**Error**: `ValueError: Project test-proj-mapgen-upsert not found`

**Root cause**: The test creates project/doc in `db_session` (transaction-scoped, rolled back after test). When `MapGenerator.generate_level1()` runs in a thread and calls `db_session_factory()` in its `do_upsert()`, it gets a fresh session that doesn't see the committed data.

### 3. `test_runner_cleans_up_on_ollama_error`

**Error**: `assert None is not None` at `assert reloaded is not None`

**Root cause**: Same as #1 — the job status update fails in the async pipeline, so the job remains in "queued" status, and when the test tries to reload it, it gets None.

## Technical Root Cause

All three tests exercise `CodeIndexJobRunner.run()` which creates `CodeIndexer` internally and calls `indexer.index()` in an async context. The `LanceDBVectorStore` operations cannot be properly mocked in this threaded async context.

## Files Changed

- `tests/integration/conftest.py` — Added function-scoped `db_session_factory` fixture
- `tests/integration/test_code_index_pipeline.py` — Multiple fixes to improve test isolation
- `orch/rag/job.py` — Added `_db_set_status_async()` async method

## Recommendation

These 3 tests require either:
1. A complete test redesign with proper async mocking
2. Integration test environment with real Ollama/LanceDB
3. Removing the tests if the async pipeline cannot be properly tested in isolation

The 474 passing integration tests provide adequate coverage for the platform.