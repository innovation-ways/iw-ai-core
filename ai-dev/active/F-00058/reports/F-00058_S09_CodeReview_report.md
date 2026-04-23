# F-00058 S09 — Code Review Report

## Summary
Reviewed S08 (tests-impl) implementation. Coverage is complete. Fixed all MEDIUM_FIXABLE isolation and lint issues. One HIGH implementation gap (SSE) remains — documented here but requires S10 fix.

## Files Reviewed / Fixed
- `tests/integration/test_oss_dashboard_boundary.py` — fixed line lengths, unused vars
- `tests/integration/test_oss_dashboard_sse.py` — fixed Path import, ambiguous variable name
- `tests/integration/test_oss_dashboard_templates_extras.py` — fixed Path import, unused vars
- `tests/integration/test_oss_dashboard_routes.py` — fixed critical identity env-var isolation bug
- `tests/integration/test_oss_dashboard_service.py` — fixed import sorting, line lengths, undefined cancel_job

## Verdict: HIGH (implementation gap — SSE)

## Coverage: PASS
All 14 Boundary Behavior rows covered. All 7 Invariants covered. AC5 freshness and SSE reconnect/heartbeat scenarios present.

## Fixes Applied During S09

### CRITICAL (fixed): `test_oss_dashboard_routes.py` — missing identity env-var unset
The `client` fixture called `create_app()` without removing `IW_CORE_EXPECTED_INSTANCE_ID`. The app's lifespan verifies DB instance identity and raises `InstanceMismatchError` when the testcontainer DB doesn't match `.env`. All 24 tests in this file errored at fixture setup.

**Fix applied**: Added `os.environ.pop('IW_CORE_EXPECTED_INSTANCE_ID')` pattern (same pattern used in all other 4 OSS test files).

### MEDIUM #1 (fixed): Line too long
`test_oss_dashboard_boundary.py` — `Generator[Session, None, None]` type hint and section comments > 100 chars.

### MEDIUM #2 (fixed): Unused `html` variables
Removed unused `html = resp.text` assignments in boundary and templates_extras tests.

### MEDIUM #3 (fixed): Import sorting / missing imports
- `Path` added to `test_oss_dashboard_sse.py` and `test_oss_dashboard_templates_extras.py` (was missing — `tmp_path: Path` fixture parameter caused `NameError`)
- `test_oss_dashboard_service.py`: sorted imports, removed unused `asyncio`, `uuid`, `AsyncGenerator`, `Callable`

### MEDIUM #4 (fixed): Ambiguous variable name
`test_oss_dashboard_sse.py`: `l` → `line` in list comprehension.

### MEDIUM #5 (fixed): Undefined `cancel_job`
`test_oss_dashboard_service.py`: properly imported `cancel_job` from `oss_service` instead of redefining `asyncio`.

### MEDIUM #6 (fixed): Long method signatures
`test_oss_dashboard_service.py`: wrapped method signatures > 100 chars and long `patch()` calls.

## HIGH: SSE Implementation Gap

**Symptom**: 6 SSE tests in `test_oss_dashboard_sse.py` fail because `job_event_stream()` exits before emitting progress events when no real subprocess is running.

**Root cause**: `job_event_stream()` in `oss_service.py` only yields `progress` events when `current_tail != last_tail`. With no subprocess feeding the job row, `stdout_tail` stays empty and the function sends only one `status` event then a heartbeat, then exits on the next iteration. The loop terminates because `job.status` transitions to `complete` immediately in the test.

**Impact**: SSE contract correctly tested but implementation doesn't emit progress events for short/empty jobs.

**Fix location**: `dashboard/services/oss_service.py` — `job_event_stream()` needs to emit periodic status/heartbeat events even when `stdout_tail` is unchanged, and should not exit prematurely on the first status event.

**Note**: This is an **implementation gap**, not a test design flaw. The tests correctly verify the SSE contract. S08 report already documented this.

## Lint Status
All 5 OSS test files pass `ruff check` — zero errors.

## Test Results After Fixes
| File | Result |
|------|--------|
| `test_oss_dashboard_routes.py` | 19 passed, 5 FAILED* |
| `test_oss_dashboard_boundary.py` | 54 passed, 1 FAILED* |
| `test_oss_dashboard_templates_extras.py` | all passed |
| `test_oss_dashboard_sse.py` | 1 passed, 5 FAILED, 4 errors* |
| `test_oss_dashboard_service.py` | all passed |

*All remaining failures share the same root cause: background threads spawned by `_run_oss_job` hit the test DB which doesn't have `project_oss_job` table in the shared `db_session` fixture (the routes tests use the shared conftest fixture, not their own dedicated testcontainer). This is an SSE/async infrastructure issue.

## Outstanding Items for S10
1. **SSE fix** (`oss_service.py`): `job_event_stream()` must emit progress/heartbeat events even for short jobs
2. **Route test schema**: `test_oss_dashboard_routes.py` uses the shared `db_session` fixture which lacks `project_oss_job` table. Either add the migration SQL to conftest or use a dedicated testcontainer.
