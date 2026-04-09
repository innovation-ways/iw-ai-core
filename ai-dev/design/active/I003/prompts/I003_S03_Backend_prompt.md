# I003_S03_Backend_prompt

**Work Item**: I003 — History Page Sorting Broken — Replace with Client-Side JS Sorting
**Step**: S03
**Agent**: Backend

---

## Input Files

- `ai-dev/design/active/I003/I003_Issue_Design.md` — Design document
- `ai-dev/design/active/I003/reports/I003_S01_Frontend_report.md` — S01 report
- `ai-dev/design/active/I003/reports/I003_S02_CodeReview_Frontend_report.md` — S02 review report

## Output Files

- `ai-dev/design/active/I003/reports/I003_S03_Backend_report.md` — Step report

## Context

You are cleaning up the backend after the Frontend agent (S01) moved sorting to client-side JavaScript. The server-side sorting and pagination infrastructure in `project_pages.py` is now dead code and must be removed.

Read the design document and prior reports first, then read `CLAUDE.md`.

## Requirements

### 1. Remove sort constants

**File**: `dashboard/routers/project_pages.py`

Remove these constants (currently around lines 37-46):
- `_SORT_COLUMNS` dict
- `_ALLOWED_SORT_BY` set
- `_ALLOWED_SORT_DIR` tuple

### 2. Simplify `_history_items()` function

**File**: `dashboard/routers/project_pages.py` (currently lines 140-223)

Remove from the function signature:
- `sort_by: str = "created_at"` parameter
- `sort_dir: str = "desc"` parameter
- `page: int` parameter

Remove from the function body:
- Sort parameter validation (lines ~153-157)
- The entire sort logic block (lines ~192-200): the `if sort_by == "duration"` branch and the `else` branch with `_SORT_COLUMNS[sort_by]`
- Pagination slicing (lines ~202-205): `all_rows`, `total`, `offset`, `page_rows`

The function should:
- Apply a sensible default ORDER BY (e.g., `WorkItem.created_at.desc()`) so items appear in a reasonable default order
- Return `(list[HistoryItem], int)` — all matching items and their count
- Execute the query and return all results (no slicing)

Also remove the `nulls_first` and `nulls_last` imports from sqlalchemy if they are no longer used anywhere in the file.

### 3. Simplify `project_history()` route handler

**File**: `dashboard/routers/project_pages.py` (currently lines 248-297)

Remove from the route function signature:
- `page: int = 1` parameter
- `sort_by: str = "created_at"` parameter
- `sort_dir: str = "desc"` parameter

Remove from the function body:
- `page` validation (`if page < 1: page = 1`)
- `page`/`sort_by`/`sort_dir` from the `_history_items()` call
- `total_pages` calculation

Remove from the template context dict:
- `page`
- `total_pages`
- `page_size`
- `sort_by`
- `sort_dir`

Keep in the template context:
- `current_project`
- `running_count`
- `items`
- `total`
- `type_filter`, `status_filter`, `date_from`, `date_to`
- `item_types`, `item_statuses`

### 4. Clean up unused imports

If `nulls_first` and `nulls_last` are no longer used anywhere in the file, remove them from the sqlalchemy import line.

## Project Conventions

Read the project's `CLAUDE.md` for:
- SQLAlchemy 2.0 sync ORM with `Mapped[]` declarative style
- Ruff linter with `line-length = 100`
- mypy strict mode

## TDD Requirement

Follow TDD (Red-Green-Refactor):
1. **RED**: Write a test verifying that `_history_items()` no longer accepts sort/page params
2. **GREEN**: Make the changes
3. **REFACTOR**: Clean up

## Test Verification (NON-NEGOTIABLE)

After implementation:
1. Run `make test-unit` — all tests must pass
2. Run `make lint` and `make format-check`
3. Run `make type-check`
4. Do **NOT** report `tests_passed: true` unless ALL checks pass

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Backend",
  "work_item": "I003",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
