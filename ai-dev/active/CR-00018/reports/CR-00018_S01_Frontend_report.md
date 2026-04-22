# CR-00018 S01 Frontend Report

## What was done

Added pagination controls to the History page (`/project/{id}/history`) which was previously only showing the first page of results (20 items) with no way to navigate to subsequent pages.

### Changes

**`dashboard/routers/project_pages.py`**
- Added `page_size` (20) to the template context in `project_history()` so the template knows the page size

**`dashboard/templates/pages/project/history.html`**
- Added a `{% if total > page_size %}` pagination block below the table
- Shows item range (e.g. `21–40 of 87`) and Prev/Next links
- URL query params preserve current filters (type, status, date_from, date_to, sort_by, sort_dir) across page navigations

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/project_pages.py` | +1 line: added `page_size` to template context |
| `dashboard/templates/pages/project/history.html` | +25 lines: pagination block |

## Test Results

- `tests/unit/test_history_sort.py`: 3 passed (filter acceptance tests)
- `tests/dashboard/` (non-browser tests): 107 passed
- `ruff` Python lint on `project_pages.py`: 1 line-length violation pre-existing (unrelated to this change, line 193)

## Observations

- The history page already had a `_HISTORY_PAGE_SIZE = 20` constant defined but it was only used for the SQL offset/limit — it was never passed to the template context, so the template couldn't render pagination controls
- The pagination pattern mirrors the existing `jobs_table.html` fragment (Prev/Next, item count, preserved filter params)
- HTML template syntax validation by ruff produces spurious errors due to Jinja2 being parsed as Python; these are false positives as confirmed by the 107 passing dashboard tests