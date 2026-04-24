# F-00060 S05 — API Report

## What Was Done

Implemented `POST /project/{project_id}/api/code/reindex-docs` endpoint in `dashboard/routers/code_ui.py` that enqueues a `DocIndexJob` for manual doc re-indexing. The endpoint:

1. Resolves project from `project_id` (404 if not found)
2. Checks if a `doc_index_jobs` row exists with `status IN ('queued', 'running')` for the project — returns 409 with an htmx fragment if so
3. Otherwise inserts a new `DocIndexJob` row with config from `CodeUnderstandingConfig` and returns 200 with the `code_job_status.html` fragment

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/code_ui.py` | Added `uuid` import, `DocIndexJob` import, and `reindex_docs` endpoint |
| `dashboard/templates/fragments/doc_job_already_running.html` | New fragment for 409 responses |
| `tests/integration/test_reindex_docs_endpoint.py` | New integration test file with 9 tests |

## Test Results

```
make lint        — All checks passed on changed files
make typecheck   — Success: no issues found (152 source files)
make test-integration (reindex docs only) — 9 passed
```

### Test Coverage

- POST no running job → 200, row created with correct config
- POST no running job → 200, fragment contains project_id
- POST when job queued → 409 with "already running" message
- POST when job running → 409
- POST unknown project → 404
- POST writes exactly one row
- POST row has correct `provider='local'`, `llm_model`, `embed_model`, `index_tier`
- POST with completed job → 200 (allowed)
- POST with failed job → 200 (allowed)

## Key Design Decisions

- Uses existing `_get_project_or_404` helper for consistency
- Config values sourced from `CodeUnderstandingConfig` via `build_code_config_from_project` (same helper as code index endpoint)
- 409 response uses `HTMLResponse` with `TemplateResponse` body decoded to string — avoids TemplateResponse defaulting to 200 status
- Does NOT launch runner — daemon poller (S04) dequeues and launches
- No new router file — endpoint added to existing `code_ui.py`

## Observations

- The `code_job_status.html` fragment is designed for code index jobs (SSE URL points to `/api/code/index/stream`). For doc index jobs, S06 will need to parameterize this fragment or create a separate doc variant.
- The 409 "already running" fragment includes a link to the Jobs view as specified.
- Existing code-reindex endpoint (`POST /api/code/reindex`) is untouched.
