# CR-00002 S01: Backend — Add sort parameters to History view

## Context

Read `CLAUDE.md` for project conventions. This is a Change Request to add sortable columns to the History table at `/project/{project_id}/history`.

## What to Change

**File**: `dashboard/routers/project_pages.py`

### 1. Add `sort_by` and `sort_dir` parameters to `_history_items()`

Add two new keyword params:
- `sort_by: str = "created_at"` — allowed values: `id`, `type`, `title`, `status`, `created_at`, `duration`
- `sort_dir: str = "desc"` — allowed values: `asc`, `desc`

**Whitelist validation**: If `sort_by` is not in the allowed set, default to `"created_at"`. If `sort_dir` is not `"asc"` or `"desc"`, default to `"desc"`.

### 2. Replace hardcoded `order_by` with dynamic sorting

Current code (line ~173):
```python
stmt = stmt.order_by(WorkItem.created_at.desc())
```

Replace with a mapping from `sort_by` values to SQLAlchemy column expressions:

```python
_SORT_COLUMNS = {
    "id": WorkItem.id,
    "type": WorkItem.type,
    "title": WorkItem.title,
    "status": WorkItem.status,
    "created_at": WorkItem.created_at,
}
```

For most columns, apply `.asc()` or `.desc()` based on `sort_dir`.

**Duration sorting**: Duration is `completed_at - created_at`, which is not a DB column. Use `WorkItem.completed_at` as the sort key for duration, with `nulls_last()` for ascending and `nulls_first()` for descending. This works because all items share the same approximate creation-to-completion correlation, and the actual computed `duration_secs` is calculated post-query anyway. Alternatively, use a SQL expression: `func.extract('epoch', WorkItem.completed_at - WorkItem.created_at)` with appropriate null handling.

### 3. Update `project_history()` route to accept sort params

Add `sort_by` and `sort_dir` query params to the route function signature:

```python
sort_by: str = "created_at",
sort_dir: str = "desc",
```

Pass them through to `_history_items()` and include them in the template context:

```python
"sort_by": sort_by,
"sort_dir": sort_dir,
```

### 4. Validate and normalize sort params

After receiving params, normalize:
```python
allowed_sort = {"id", "type", "title", "status", "created_at", "duration"}
if sort_by not in allowed_sort:
    sort_by = "created_at"
if sort_dir not in ("asc", "desc"):
    sort_dir = "desc"
```

## TDD Approach

Write a failing test first:

1. **RED**: Write a test in `tests/integration/` that calls `_history_items()` with `sort_by="title"` and `sort_dir="asc"` and asserts the results are alphabetically ordered by title
2. **GREEN**: Implement the sorting logic to make the test pass
3. **REFACTOR**: Clean up the implementation

## Files to Modify

- `dashboard/routers/project_pages.py` — `_history_items()` and `project_history()` functions

## Acceptance Criteria

- `_history_items()` accepts `sort_by` and `sort_dir` params with safe defaults
- Invalid `sort_by`/`sort_dir` values fall back to defaults (no errors)
- All 6 sort columns produce correctly ordered results
- Duration sort handles NULL `completed_at` gracefully
- Template context includes `sort_by` and `sort_dir` values
- Existing behavior unchanged when no sort params provided
