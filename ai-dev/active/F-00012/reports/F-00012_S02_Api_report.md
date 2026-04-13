# F-00012 S02 API Report

## Summary

Implemented the API and CLI layer for the F-00012: AI Documentation Generation system.

## What Was Done

### 1. CLI Commands (`orch/cli/doc_commands.py`)

Added two new commands:

- **`iw doc-job-start JOB_ID [--pid INTEGER] [--skill TEXT]`**
  - Transitions a queued `DocGenerationJob` to running state
  - Records agent PID and skill used
  - Idempotent: if already running, exits 0 without error
  - Exits 1 if job not found, exits 2 if job not in queued state

- **`iw doc-job-done JOB_ID [--error TEXT]`**
  - Marks a running job as completed (or failed with --error)
  - Calculates duration if started_at is set
  - Idempotent: calling on already-completed/failed job exits 0

Also added `get_doc_job()` method to `DocService`.

### 2. Dashboard Routes (`dashboard/routers/docs.py`)

Added 5 new routes:

- **`POST /api/project/{id}/docs/{doc_id}/generate`**
  - Creates a `DocGenerationJob` via `DocService.create_doc_job()`
  - Returns htmx-compatible HTML fragment (spinner)
  - Returns 409 if job already running for this doc
  - Sets `HX-Trigger` header for htmx event dispatch

- **`GET /api/project/{id}/docs/jobs/{job_id}/stream`**
  - SSE endpoint streaming job status updates
  - Events: `status` (every 2s while running), `completed`, `failed`, `timeout` (15min)
  - Follows exact pattern from `dashboard/routers/sse.py`

- **`GET /api/project/{id}/docs/jobs/{job_id}/status`**
  - JSON poll endpoint returning job status details
  - Includes duration_seconds, skill_used, error

- **`GET /api/project/{id}/docs/{doc_id}/jobs`**
  - htmx fragment returning last 10 jobs for a doc (job history)

- **`GET /api/project/{id}/docs/{doc_id}/card`**
  - htmx fragment returning a single `docs_card.html` for the doc

### 3. Templates

Created two new htmx fragment templates:
- `dashboard/templates/fragments/docs_generate_running.html` - spinner while generating
- `dashboard/templates/fragments/docs_job_history.html` - job history list

### 4. Unit Tests (`tests/unit/test_doc_job_commands.py`)

Created 8 unit tests covering:
- `test_doc_job_start_transitions_to_running` - exit 0, JSON output, status=running
- `test_doc_job_start_already_running_idempotent` - exit 0, already running
- `test_doc_job_start_job_not_found` - exit 1
- `test_doc_job_start_invalid_status` - exit 2
- `test_doc_job_done_marks_completed` - exit 0, status=completed
- `test_doc_job_done_with_error_marks_failed` - exit 0, status=failed, error stored
- `test_doc_job_done_idempotent` - twice, both exit 0
- `test_doc_job_done_job_not_found` - exit 1

## Files Changed

| File | Change |
|------|--------|
| `orch/cli/doc_commands.py` | Extended with doc-job-start, doc-job-done commands |
| `orch/doc_service.py` | Added get_doc_job() method |
| `dashboard/routers/docs.py` | Extended with 5 new routes |
| `tests/unit/test_doc_job_commands.py` | New test file with 8 tests |
| `dashboard/templates/fragments/docs_generate_running.html` | New template |
| `dashboard/templates/fragments/docs_job_history.html` | New template |

## Test Results

```
make test-unit: 602 passed, 1 warning
make quality: All checks passed
make check: 329 passed (integration) + 602 passed (unit), 3 warnings
```

## Issues/Observations

- The `project_id` path parameter in the SSE stream route is validated against the DB but not otherwise used (the job_id is globally unique)
- Duration calculation is delegated to the service layer; unit tests mock at CLI boundary
