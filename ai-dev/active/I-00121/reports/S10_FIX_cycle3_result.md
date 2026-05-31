# I-00121 S10 QV Fix Cycle 3/5 — Result Contract

## Implementation Status: COMPLETE ✅

The implementation specified in the design doc is complete and correct. All tests in my allowed scope pass.

## Tests in Allowed Scope (all PASS)

```
tests/unit/test_test_runner_allure_env.py        — 10 passed
tests/integration/test_test_runner_report_persistence.py — 3 passed
```

## Blocker: Docker/Testcontainer Infrastructure Failures

The `make test-unit` gate runs ALL 3722 unit tests. 44 tests fail with Docker errors
in files OUTSIDE my allowed_paths:

| File | Tests Failing | Root Cause |
|------|-------------|------------|
| `tests/unit/test_jobs_aggregator.py` | 10 | Docker port conflict (address already in use) |
| `tests/unit/chat/test_tab_service_allowlist.py` | 5 | Docker/internal server error |
| `tests/unit/chat/test_tab_service.py` | 10 | Docker/internal server error |
| `tests/unit/db/test_chat_conversation_model.py` | 3 | Docker/internal server error |
| `tests/unit/db/test_work_item_impacted_paths.py` | 3 | Docker/internal server error |
| `tests/unit/db/test_chat_message_model.py` | 3 | Docker/internal server error |
| `tests/unit/db/test_chat_summarization_job_model.py` | 2 | Docker/internal server error |
| `tests/unit/properties/test_health_service_properties.py` |1 | Docker/internal server error |
| `tests/unit/test_no_key_path_unchanged` | 1 | Docker/internal server error |
| `tests/unit/test_health_service.py` | 7 | Docker/internal server error |

**Total: 44 errors out of 3722 tests** (3664 passed, 6 skipped, 7 xfailed, 1 xpassed)

## Root Cause

The failing tests use `testcontainers.postgres.PostgresContainer` which requires Docker.
These tests fail with:
- `docker.errors.APIError: 500 Server Error: Internal Server Error`
- `Address already in use` (port conflicts between concurrent containers)

This is an **infrastructure issue**, not a code issue. The tests in my scope do NOT use Docker.

## Required Out-of-Scope Fix

To make `make test-unit` pass, one of these is needed:

1. **Option A (recommended)**: Amend `allowed_paths` to include the failing test files, then add `@pytest.mark.skip(reason="Docker unavailable in CI")` decorators or convert to use `db_session` fixture (testcontainer-less pattern)

2. **Option B**: Modify `Makefile` to exclude Docker-dependent tests from `test-unit`:
   ```makefile
   test-unit:
       uv run pytest tests/unit/ $(COV_FLAGS) -v \
           --ignore=tests/unit/test_jobs_aggregator.py \
           --ignore=tests/unit/chat/test_tab_service*.py \
           --ignore=tests/unit/db/test_chat_*.py \
           --ignore=tests/unit/properties/test_health_service_properties.py \
           --ignore=tests/unit/test_health_service.py
   ```

3. **Option C**: Fix Docker environment (stop conflicting containers, increase port range)

## Files That Need Amended allowed_paths

```
tests/unit/test_jobs_aggregator.py
tests/unit/chat/test_tab_service_allowlist.py
tests/unit/chat/test_tab_service.py
tests/unit/db/test_chat_conversation_model.py
tests/unit/db/test_chat_message_model.py
tests/unit/db/test_chat_summarization_job_model.py
tests/unit/db/test_work_item_impacted_paths.py
tests/unit/properties/test_health_service_properties.py
tests/unit/test_health_service.py
```

## Implementation Verification

```bash
# Tests in my scope pass:
$ uv run pytest tests/unit/test_test_runner_allure_env.py tests/integration/test_test_runner_report_persistence.py -v
========================13 passed, 2 warnings in 7.17s ========================

# Lint/format on scoped files:
$ make format-check
No violations in scoped files

$ uv run ruff check orch/test_runner.py tests/unit/test_test_runner_allure_env.py tests/integration/test_test_runner_report_persistence.py
All checks passed!
```

## Result

**Status**: BLOCKED by infrastructure (Docker unavailable for unrelated test files)

**Fix needed**: Operator must either amend allowed_paths to include failing test files, or modify the Makefile to exclude Docker-dependent tests from the unit-test gate.
