# CR-00002: Add sortable columns to History table

**Type**: Change Request
**Priority**: Medium
**Reason**: Usability — users need to sort history items by different columns to find specific items quickly
**Created**: 2026-04-09
**Status**: Draft

---

## Description

Add clickable sort controls to all 6 column headers (ID, Type, Title, Status, Date, Duration) in the History view table. Sorting is server-side via query parameters, preserving compatibility with existing pagination and filters.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

## Current Behavior

The History page (`/project/{project_id}/history`) renders a table of completed/failed work items with 6 columns: ID, Type, Title, Status, Date, Duration. The table is always sorted by `created_at` descending. Column headers are plain text with no interactive behavior.

Key files:
- **Route**: `dashboard/routers/project_pages.py` lines 221-264 — `project_history()` handler
- **Query helper**: `dashboard/routers/project_pages.py` lines 129-196 — `_history_items()` function, hardcoded `order_by(WorkItem.created_at.desc())`
- **Template**: `dashboard/templates/pages/project/history.html` — static `<th>` headers, pagination links preserve filter params but no sort params

## Desired Behavior

1. Each column header displays a clickable sort link
2. Clicking a header sorts by that column ascending; clicking again toggles to descending
3. The currently active sort column shows a visual indicator (▲ for asc, ▼ for desc)
4. Sort state is preserved across pagination and filter changes via `sort_by` and `sort_dir` query parameters
5. Default sort remains `created_at` descending (Date column, desc) when no sort params are provided
6. Allowed `sort_by` values: `id`, `type`, `title`, `status`, `created_at`, `duration`
7. Duration sorting treats NULL durations as largest (sorts to end in ascending, beginning in descending)

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `_history_items()` helper | Hardcoded `order_by(created_at.desc())` | Dynamic `order_by()` based on `sort_by`/`sort_dir` params |
| `project_history()` route | No sort params | Accepts `sort_by` and `sort_dir` query params |
| History template `<thead>` | Plain text headers | Clickable sort links with direction indicators |
| History template pagination | Preserves filter params only | Also preserves `sort_by` and `sort_dir` params |
| History template filter form | No sort hidden inputs | Includes hidden inputs for current sort state |

### Breaking Changes

- None — new query params are optional with backward-compatible defaults

### Data Migration

- None

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add `sort_by`/`sort_dir` params to `_history_items()` and `project_history()`, pass sort context to template | — |
| S02 | CodeReview | Review S01 output | — |
| S03 | frontend-impl | Update template: sortable headers with links/indicators, preserve sort in pagination/filters | — |
| S04 | CodeReview | Review S03 output | — |
| S05 | tests-impl | Add unit tests for sort param validation and integration tests for sorted query results | — |
| S06 | CodeReview | Review S05 output | — |
| S07 | CodeReview_Final | Global review of all work | — |
| S08 | QV-lint | `ruff check` | — |
| S09 | QV-format | `ruff format --check` | — |
| S10 | QV-typecheck | `mypy` | — |
| S11 | QV-unit-tests | `make test-unit` | — |
| S12 | QV-integration-tests | `make test-integration` | — |
| S13 | QV-browser | Visual verification of sortable headers in browser | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — sorting uses existing columns

### API Changes

- **New endpoints**: None
- **Modified endpoints**: `GET /project/{project_id}/history` — adds optional `sort_by` (str) and `sort_dir` (str, "asc"/"desc") query params
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None — sort header macro added inline or as a small Jinja2 macro
- **Modified components**: `dashboard/templates/pages/project/history.html` — `<thead>`, pagination links, filter form
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/design/active/CR-00002/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00002_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00002_S01_Backend_prompt.md` | Prompt | Backend sort logic implementation |
| `prompts/CR-00002_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00002_S03_Frontend_prompt.md` | Prompt | Template sort UI implementation |
| `prompts/CR-00002_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00002_S05_Tests_prompt.md` | Prompt | Test coverage for sorting |
| `prompts/CR-00002_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00002_S07_CodeReview_Final_prompt.md` | Prompt | Global review |

Reports are created during execution in `ai-dev/work/CR-00002/reports/`.

## Acceptance Criteria

### AC1: Column headers are clickable sort links

```
Given the History page is loaded
When the user clicks the "ID" column header
Then the table re-renders sorted by ID ascending, and the ID header shows ▲
```

### AC2: Toggle sort direction on repeated click

```
Given the History table is sorted by Date ascending
When the user clicks the "Date" column header again
Then the table re-renders sorted by Date descending, and the Date header shows ▼
```

### AC3: Sort state preserved across pagination

```
Given the table is sorted by Title ascending and has multiple pages
When the user clicks "Next" to go to page 2
Then page 2 is still sorted by Title ascending
```

### AC4: Sort state preserved with filters

```
Given the table is sorted by Duration descending
When the user applies a Type filter
Then the filtered results are still sorted by Duration descending
```

### AC5: Default sort unchanged

```
Given no sort_by or sort_dir query params
When the History page loads
Then items are sorted by Date (created_at) descending (existing behavior)
```

### AC6: NULL duration handling

```
Given some items have no completed_at (NULL duration)
When sorted by Duration ascending
Then NULL-duration items appear last
```

## Rollback Plan

- **Database**: Not applicable — no schema changes
- **Code**: Revert commit; the old hardcoded sort behavior is fully restored
- **Data**: No data impact

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- Unit tests: Validate `sort_by` param whitelist, `sort_dir` defaults, invalid param handling
- Integration tests: Query returns correctly ordered results for each sortable column in both directions; NULL duration ordering
- Updated tests: `tests/integration/test_dashboard_remaining.py` if it tests history page rendering

## Notes

- Server-side sorting is the correct approach since client-side sorting would only sort the current page (20 items), not the full dataset
- The `sort_by` whitelist (`id`, `type`, `title`, `status`, `created_at`, `duration`) prevents SQL injection via arbitrary column names
- Duration sorting requires special handling since `duration_secs` is computed (not a DB column) — the backend should use `completed_at - created_at` or `COALESCE(completed_at, '9999-12-31')` for ordering
