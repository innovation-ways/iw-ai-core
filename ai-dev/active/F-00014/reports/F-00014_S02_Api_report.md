# F-00014 S02 API Report

## What Was Done

Implemented the API layer for F-00014 (Documentation Polish — Phase 4). Extended `dashboard/routers/docs.py` with four new routes and created a new `dashboard/routers/docs_global.py` router for cross-project documentation search.

## Files Changed

### Modified
- `dashboard/routers/docs.py` — Added four new routes:
  - `GET /api/docs/{doc_id}/diff?v1={n}&v2={m}` — Returns `docs_diff.html` fragment with unified diff; 404 if doc/version not found, 422 if v1 >= v2, empty-state fragment if no diff
  - `GET /api/docs/export?doc_ids={csv}` — Bulk ZIP export via `DocService.export_bundle()`; exports all docs if `doc_ids` is empty
  - `GET /api/docs/{doc_id}/export` — Single-doc ZIP export; filename `{slug}-v{version}.zip`
  - `GET /api/docs/{doc_id}/validate-links` — Async route (runs `validate_links` via `asyncio.to_thread`); returns `docs_broken_links.html` fragment
- `dashboard/app.py` — Registered `docs_global` router

### Created
- `dashboard/routers/docs_global.py` — Global docs search router:
  - `GET /docs` — Full-page global search (no project prefix)
  - `GET /api/docs/search` — htmx fragment; results grouped by project
- `dashboard/templates/fragments/docs_diff.html` — Diff fragment with colored unified diff lines
- `dashboard/templates/fragments/docs_broken_links.html` — Broken links callout (red) or all-clear (green)
- `dashboard/templates/fragments/docs_global_results.html` — Global search results grouped by project
- `dashboard/templates/docs_global.html` — Full-page global docs search (extends base.html) with filter dropdowns

## Test Results

- `make quality` (ruff check): All checks passed
- `make quality` (ruff format): 142 files already formatted
- `make quality` (mypy): 1 pre-existing error in `orch/doc_service.py` (missing `types-PyYAML` stubs) — not introduced by this step. No new errors.

## Notes

- All routes follow the existing `docs.py` conventions: thin handlers, `DocService` for business logic, `_get_project_or_404` for project validation
- Export routes use `io.BytesIO` with `StreamingResponse` as specified
- `validate-links` uses `asyncio.to_thread` to avoid blocking the event loop
- The `docs_global` router is registered with no prefix so `/docs` and `/api/docs/search` are top-level routes
- The pre-existing `yaml` mypy error is unchanged from before this step
