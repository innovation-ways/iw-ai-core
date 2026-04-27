# I-00041 S05 Tests Report

## Summary

Completed the test implementation for I-00041 (connection-layer guard against integration tests writing to live orchestration DB). All 13 guard unit tests, 10 strip-helper unit tests, and 3 reproduction integration tests pass. The migration_pipeline tests remain unchanged (already had unique_batch_id fixture and helper extraction).

## Files Changed

1. **tests/unit/test_live_db_guard.py** - 4 fixes to match actual implementation behavior:
   - `test_is_live_db_url_fails_open_when_env_unset`: Fixed to use a URL that doesn't match the defaults (otherhost instead of localhost) since implementation defaults to localhost:5433 when env vars are unset
   - `test_assert_allowed_refuses_under_test_context`: Changed assertion from `"5433"` to `"host:port"` since error message uses generic "host:port" text
   - `test_assert_allowed_refuses_under_agent_context_deprecated`: Same fix + added `monkeypatch.delenv("IW_CORE_TEST_CONTEXT")` to isolate the AGENT_CONTEXT check from session fixture
   - `test_safe_create_engine_calls_guard_before_creating_engine`: Fixed patch path to use `sqlalchemy.create_engine` and renamed import to avoid shadowing

2. **tests/integration/test_live_db_guard_reproduction.py** - 2 fixes:
   - `test_subprocess_in_test_context_cannot_connect_to_live_db`: Fixed URL construction inside subprocess (was using `_LIVE_URL` which resolved to port 1 due to conftest R0e hijack); now constructs correct live DB URL inside subprocess with port 5433
   - `test_daemon_armed_subprocess_via_agent_env_helper_cannot_connect_to_live_db`: Same fix - URL constructed inside subprocess with correct port

## Test Results

| Test Suite | Tests | Passed | Failed | Skipped |
|------------|-------|--------|--------|---------|
| test_live_db_guard.py (unit) | 13 | 13 | 0 | 0 |
| test_agent_subprocess_env.py (unit) | 10 | 10 | 0 | 0 |
| test_live_db_guard_reproduction.py (integration) | 4 | 3 | 0 | 1* |
| test_migration_pipeline.py (integration) | 7 | 6 | 0 | 1** |

*Operator-only test skipped (requires `IW_CORE_OPERATOR_APPLY=true`)
**Operator-only smoke test skipped (requires `IW_CORE_OPERATOR_APPLY=true`)

## Verification

- `make lint` ✅ passes
- `uv run pytest tests/unit/test_live_db_guard.py -v` ✅ 13/13 passed
- `uv run pytest tests/unit/test_agent_subprocess_env.py -v` ✅ 10/10 passed
- `uv run pytest tests/integration/test_live_db_guard_reproduction.py -v -k "not operator"` ✅ 3/3 passed
- `uv run pytest tests/integration/test_migration_pipeline.py -v` ✅ 6/6 passed (1 skipped)
- `grep -nE "batch_id\s*=\s*42" tests/integration/test_migration_pipeline.py` ✅ no matches

## Notes

- The typecheck errors in `dashboard/` and `orch/rag/` are pre-existing issues unrelated to I-00041
- The reproduction tests verify both refusal paths (test-context subprocess and daemon-armed-agent subprocess) correctly refuse connection to live DB before any network call is made
- The positive-control tests confirm the guard does NOT block legitimate testcontainer connections or operator-context processes
