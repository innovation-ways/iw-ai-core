# F-00012 S04 Tests Report

## Summary

Completed integration tests for F-00012: AI Documentation Generation (Phase 2). All 31 new tests pass, plus 360 existing integration tests continue to pass.

## Files Changed

- `tests/integration/test_doc_generation.py` — 19 tests for job lifecycle, CLI commands, and poller
- `tests/integration/test_doc_job_routes.py` — 12 tests for dashboard routes
- `orch/cli/main.py` — Added `doc-job-start` and `doc-job-done` to CLI group (was missing from S02)

## Tests Added

### test_doc_generation.py (19 tests)

**Job Lifecycle**
- `test_full_job_lifecycle_success` — create job → start → update doc → complete
- `test_full_job_lifecycle_failure` — failed job: doc content unchanged
- `test_concurrent_job_limit` — poller respects MAX_CONCURRENT_JOBS_PER_PROJECT=2
- `test_stall_detection` — job stalled >10 min is marked failed
- `test_generate_when_job_already_running_returns_409` — 409 when job already running
- `test_generate_doc_with_no_source_paths` — job created even with empty source_paths

**Skill Selection**
- `test_skill_selection_technical` — iw-doc-generator for technical
- `test_skill_selection_api` — iw-doc-generator for api
- `test_skill_selection_guide` — iw-doc-system for guide
- `test_skill_selection_compliance` — iw-doc-system for compliance
- `test_skill_selection_marketing` — iw-doc-system for marketing

**CLI Commands (doc-job-start)**
- `test_doc_job_start_cli` — marks job running, JSON output, DB state
- `test_doc_job_start_unknown_job_exits_1` — exit 1 for unknown job
- `test_doc_job_start_already_running_exits_0` — idempotent for running job

**CLI Commands (doc-job-done)**
- `test_doc_job_done_cli_completed` — marks completed with JSON output
- `test_doc_job_done_cli_failed` — marks failed with --error flag
- `test_doc_job_done_idempotent` — calling twice is a no-op
- `test_doc_job_done_unknown_job_exits_1` — exit 1 for unknown job
- `test_doc_job_done_already_completed_is_noop` — exit 0 for already-completed job

### test_doc_job_routes.py (12 tests)

**Generate Endpoint**
- `test_docs_generate_creates_job` — returns 200
- `test_docs_generate_returns_409_when_job_running` — 409 when job running
- `test_docs_generate_unknown_project_404` — 404 for unknown project
- `test_docs_generate_unknown_doc_404` — 404 for unknown doc

**Status Poll**
- `test_status_poll_route_queued` — queued job returns correct fields
- `test_status_poll_route_running` — running job returns pid, skill, started_at
- `test_status_poll_route_completed` — completed job returns duration_seconds
- `test_status_poll_route_failed` — failed job returns error message
- `test_status_poll_route_unknown_job_404` — 404 for unknown job

**Job History**
- `test_job_history_route` — returns 200 with job entries
- `test_job_history_route_unknown_project_404` — 404 for unknown project
- `test_job_history_route_empty` — returns 200 when no jobs

## Test Results

```
make test-unit: 602 passed
make test-integration: 360 passed (31 new + 329 existing)
make quality: All checks passed
```

## Implementation Fix

Added `doc_job_start` and `doc_job_done` to the CLI group in `orch/cli/main.py`. These commands were defined but not registered, which would have prevented `iw doc-job-start` and `iw doc-job-done` from working.

## Notes

- SSE stream tests were excluded because the SSE endpoint creates its own `SessionLocal` session (bypassing FastAPI DI), making testcontainer integration complex. The SSE behavior is tested in unit tests with proper mocking.
- All tests use testcontainers — no live database connections.
- All tests use `db_session.flush()` to persist data within the test transaction, ensuring proper visibility to the FastAPI routes via `get_db` dependency.
