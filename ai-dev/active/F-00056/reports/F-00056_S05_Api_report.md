# F-00056 S05 API Report

## Summary

Added two execution report dashboard routes to `dashboard/routers/items.py` that surface the `ExecutionReportData` assembled by `assemble_execution_report()` (from `orch/daemon/execution_report.py`, implemented in S03).

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/items.py` | Added import for `assemble_execution_report`; added `item_tab_execution_report()` and `item_execution_report_page()` |
| `dashboard/templates/fragments/item_execution_report.html` | Stub fragment (S07 replaces) |
| `dashboard/templates/pages/project/item_execution_report.html` | Stub full page (S07 replaces) |
| `tests/integration/test_execution_report_dashboard_route.py` | New: 4 tests (tab+page × 200/404) |

## Route Details

- **`GET /project/{project_id}/item/{work_item_id}/tab/execution-report`** — htmx tab fragment, renders `fragments/item_execution_report.html`
- **`GET /project/{project_id}/item/{work_item_id}/execution-report`** — standalone page, renders `pages/project/item_execution_report.html`

Both routes:
- Use existing `_get_project_or_404()` / `_get_item_or_404()` helpers for 404 handling (matching sibling pattern)
- Use `Depends(get_db)` session injection (matching all other item tab routes)
- Call `assemble_execution_report(db, project_id, work_item_id)` and pass `execution_report` + `item` + `project_id` as template context
- Return `HTMLResponse` with `response_class=HTMLResponse`

## Test Results

```
tests/integration/test_execution_report_dashboard_route.py
  test_execution_report_tab_returns_200_for_known_item      PASSED
  test_execution_report_tab_returns_404_for_unknown_item   PASSED
  test_execution_report_page_returns_200_for_known_item    PASSED
  test_execution_report_page_returns_404_for_unknown_item  PASSED

1006 passed, 0 failed (unit tests)
7 passed, 0 failed (dashboard fragments)
4 passed, 0 failed (execution report routes)
```

## Linting

- `ruff check dashboard/routers/items.py` — All checks passed
- `mypy dashboard/routers/items.py` — Success: no issues found

## Notes

- Pre-existing mypy/ruff errors in `dashboard/routers/code_qa.py` are unrelated to this change
- Stub templates will be replaced by full templates in S07
- Routes are purely additive; no existing routes or templates were modified
