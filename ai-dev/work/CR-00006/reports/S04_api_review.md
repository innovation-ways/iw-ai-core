# CR-00006 S04 — API Review Report

## What Was Done

Reviewed S03 API implementation: three new routes in `jobs_ui.py`, SSE toast map extension in `sse.py`, and router registration in `app.py`.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/jobs_ui.py` | New router — 3 routes: `GET /jobs`, `GET /jobs/fragment/table`, `GET /jobs/{job_type}/{job_id}` |
| `dashboard/routers/sse.py` | Added `code_map_completed` to `_TOAST_EVENTS` (line 91) and `_TOAST_SEVERITY` (line 137) |
| `dashboard/app.py` | Added `jobs_ui` import (line 27) and `app.include_router(jobs_ui.router)` (line 147) |

## Review Checklist Results

### `dashboard/routers/jobs_ui.py`
- [x] Router prefix `"/project/{project_id}"` — matches `code_ui.py` convention
- [x] Three routes registered: `GET /jobs`, `GET /jobs/fragment/table`, `GET /jobs/{job_type}/{job_id}`
- [x] `job_type` typed as `Literal["code_mapping", "doc_generation", "batch_execution", "research"]` — invalid values return 422
- [x] Query params: `type`/`status` are list-valued (`Query()`), `page` has `ge=1`, `sort_by`/`sort_dir` use `Literal`
- [x] Missing project → HTTP 404 with `"Project not found"`
- [x] Missing job → HTTP 404 with `"Job not found"`
- [x] Invalid date format → HTTP 422 via `_parse_date`
- [x] Unknown `type`/`status` values → HTTP 422 via FastAPI/Pydantic `Literal`/enum enforcement
- [x] List page renders `pages/project/jobs.html`
- [x] Fragment renders `fragments/jobs_table.html` — does not extend `base.html`
- [x] Detail page renders `pages/project/job_detail.html`
- [x] No business logic — all delegation to `JobsAggregator`
- [x] No direct DB queries beyond `_get_project_or_404`
- [x] Template references match S05 filenames: `pages/project/jobs.html`, `pages/project/job_detail.html`, `fragments/jobs_table.html`
- [x] `ruff check` clean
- [x] `mypy` clean

### `dashboard/routers/sse.py`
- [x] `code_map_completed` added to `_TOAST_EVENTS` exactly once (line 91)
- [x] `code_map_completed: "success"` added to `_TOAST_SEVERITY` exactly once (line 137)
- [x] Not added to `_RUNNING_UPDATE_EVENTS`, `_STATUS_UPDATE_EVENTS`, `_TEST_UPDATE_EVENTS`, `_QUALITY_UPDATE_EVENTS`
- [x] `_WATCHED_EVENTS` union automatically includes the new event via existing `|` composition

### `dashboard/app.py`
- [x] `from dashboard.routers import jobs_ui` in import block (line 27)
- [x] `app.include_router(jobs_ui.router)` registered (line 147)
- [x] No other imports or calls reordered

### Route Discovery Smoke-Test
```
/project/{project_id}/jobs
/project/{project_id}/jobs/fragment/table
/project/{project_id}/jobs/{job_type}/{job_id}
```
All three routes registered correctly.

## Issues Found

None. All checklist items passed.

## Summary

API review passed. All routes have correct typing and error contracts, SSE toast map extended with `code_map_completed=success`, `jobs_ui` router wired in `dashboard/app.py`.
