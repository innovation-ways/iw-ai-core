# CR-00006 S03 — API Implementation Report

## Summary

Added dashboard routes for the JobsAggregator service and extended the SSE toast event map.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/jobs_ui.py` | **New** — 3 routes: list page, table fragment, job detail |
| `dashboard/routers/sse.py` | Added `code_map_completed` to toast events + severity map |
| `dashboard/app.py` | Registered `jobs_ui` router (import + include_router) |

## What Was Implemented

### `dashboard/routers/jobs_ui.py`
- `GET /project/{project_id}/jobs` — full page listing with filter/pagination params
- `GET /project/{project_id}/jobs/fragment/table` — htmx partial fragment response
- `GET /project/{project_id}/jobs/{job_type}/{job_id}` — job detail page (job_type is Literal)

Query params follow the same patterns as `project_pages.py:238-282`:
- `type` (repeatable, maps to `JobType[]`)
- `status` (repeatable)
- `date_from`, `date_to` (ISO date strings)
- `page` (int ≥ 1, 422 if < 1)
- `sort_by`, `sort_dir`

Uses `_get_project_or_404` pattern from `code_ui.py:32-36` for 404 handling.

### `dashboard/routers/sse.py`
- Added `"code_map_completed"` to `_TOAST_EVENTS` (lifecycle-events cluster)
- Added `"code_map_completed": "success"` to `_TOAST_SEVERITY`

### `dashboard/app.py`
- Added `jobs_ui` import (alphabetically between `items` and `project_dashboard`)
- Added `app.include_router(jobs_ui.router)` (after `research.router`)

## Verification

```bash
uv run ruff check dashboard/routers/jobs_ui.py dashboard/routers/sse.py dashboard/app.py  # PASSED
uv run mypy dashboard/routers/jobs_ui.py  # PASSED
grep -n "code_map_completed" dashboard/routers/sse.py  # 2 occurrences
grep -n "jobs_ui" dashboard/app.py  # 2 occurrences (import + include_router)
```

Route registration verification:
```
['/project/{project_id}/jobs',
 '/project/{project_id}/jobs/fragment/table',
 '/project/{project_id}/jobs/{job_type}/{job_id}']
```

## Notes

- Templates (`jobs.html`, `job_detail.html`, `jobs_table.html`) will be created in S05 — routes will 500 on render until then, which is expected
- `type` parameter uses `# noqa: A002` to suppress builtin shadowing warning (same pattern as `project_pages.py:243`)
- `Session` imported via `TYPE_CHECKING` block (same pattern as `project_pages.py:25-27`)
