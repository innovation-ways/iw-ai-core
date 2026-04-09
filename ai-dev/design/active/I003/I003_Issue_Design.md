# I003: History Page Sorting Broken — Replace with Client-Side JS Sorting

**Type**: Issue
**Severity**: Medium
**Created**: 2026-04-09
**Reported By**: User report
**Status**: Draft

---

## Description

The History page table sorting is completely non-functional from the user's perspective. Clicking column headers triggers full page reloads via server-side `<a>` links instead of sorting instantly. The batches page (`/project/{id}/batches`) has working client-side JS sorting with no backend interaction — the history page should use the identical pattern.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

## Steps to Reproduce

1. Navigate to `http://iw-dev-01:9900/project/iw-ai-core/history`
2. Click any column header (ID, Type, Title, Status, Date, Duration)
3. Observe page reloads but sorting appears non-functional

**Expected**: Clicking a column header instantly sorts the table client-side (no page reload), with a visual chevron indicator showing sort direction — identical to the batches page behavior.

**Actual**: Clicking triggers a full page reload via `<a href="?sort_by=...&sort_dir=...">` links. Sorting feels broken and unresponsive.

## Root Cause Analysis

The history page uses a Jinja2 `sort_header` macro (`history.html:4-16`) that renders `<a>` tags with `?sort_by=...&sort_dir=...` query parameters. Each click causes a full server round-trip:

1. **Template** (`history.html:4-16`): `sort_header` macro wraps column labels in `<a>` tags pointing to `?sort_by={key}&sort_dir={dir}` URLs
2. **Route handler** (`project_pages.py:248-297`): Reads `sort_by`/`sort_dir` query params, passes them to `_history_items()`
3. **Backend logic** (`project_pages.py:140-223`): `_history_items()` applies SQL `ORDER BY` based on sort params, with a buggy duration sort (sorts by `completed_at` instead of actual duration)
4. **Supporting constants** (`project_pages.py:37-46`): `_SORT_COLUMNS`, `_ALLOWED_SORT_BY`, `_ALLOWED_SORT_DIR`

The batches page (`batches.html:106-154`) uses a completely different approach:
- Each `<tr>` has `data-sort-*` attributes stamped at render time
- Each `<th>` has `onclick="sortTable('key')"` 
- A self-contained `sortTable()` JS function sorts rows client-side
- SVG chevron icons show sort direction
- Zero server interaction for sorting

Additionally, the history page has server-side pagination (20 items/page) which conflicts with client-side sorting. The fix removes pagination to load all items (matching the batches page pattern).

## Browser Evidence

Deferred — will be captured during QV Browser verification step.

## Affected Components

| Component | Impact |
|-----------|--------|
| Frontend template (`history.html`) | Replace `sort_header` macro with client-side sortable `<th>` elements, add `data-sort-*` attributes, add inline JS `sortTable()`, remove pagination UI |
| Backend route (`project_pages.py`) | Remove `sort_by`/`sort_dir` params from route and `_history_items()`, remove pagination, remove sort constants |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Replace sort_header macro with client-side JS sorting (batches pattern), add `data-sort-*` attributes to rows, remove pagination UI, add inline sortTable() JS | — |
| S02 | CodeReview_Frontend | Review S01 output | — |
| S03 | Backend | Remove `sort_by`/`sort_dir` params from `_history_items()` and route handler, remove `_SORT_COLUMNS`/`_ALLOWED_SORT_BY`/`_ALLOWED_SORT_DIR` constants, remove pagination logic | — |
| S04 | CodeReview_Backend | Review S03 output | — |
| S05 | Tests | Reproduction test + regression tests | — |
| S06 | CodeReview_Tests | Review S05 output | — |
| S07 | CodeReview_Final | Global review of all work | — |
| S08 | QV Gate | lint | — |
| S09 | QV Gate | format | — |
| S10 | QV Gate | typecheck | — |
| S11 | QV Gate | unit-tests | — |
| S12 | QV Gate | integration-tests | — |
| S13 | QV Browser | Browser verification | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No database changes required

### Code Changes

- **Files to modify**:
  - `dashboard/templates/pages/project/history.html` — Full rewrite of sorting mechanism + remove pagination
  - `dashboard/routers/project_pages.py` — Remove sort/pagination params from `_history_items()` and `project_history()` route
- **Nature of change**: Replace server-side sort+pagination with client-side JS sorting (no pagination)

## File Manifest

All files for this work item live under `ai-dev/design/active/I003/`:

| File | Type | Purpose |
|------|------|---------|
| `I003_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I003_S01_Frontend_prompt.md` | Prompt | S01 frontend fix instructions |
| `prompts/I003_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 code review |
| `prompts/I003_S03_Backend_prompt.md` | Prompt | S03 backend cleanup |
| `prompts/I003_S04_CodeReview_Backend_prompt.md` | Prompt | S04 code review |
| `prompts/I003_S05_Tests_prompt.md` | Prompt | S05 test instructions |
| `prompts/I003_S06_CodeReview_Tests_prompt.md` | Prompt | S06 code review |
| `prompts/I003_S07_CodeReview_Final_prompt.md` | Prompt | S07 global review |
| `prompts/I003_S13_QV_Browser_prompt.md` | Prompt | S13 browser verification |

Reports are created during execution in `ai-dev/design/active/I003/reports/`.

## Test to Reproduce

```python
def test_i003_history_page_no_server_sort_params():
    """History endpoint should NOT accept sort_by/sort_dir params.
    
    This test should FAIL before the fix (endpoint accepts sort params)
    and PASS after (params removed, sorting is client-side only).
    """
    # Arrange
    client = TestClient(app)
    
    # Act — request with sort params
    response = client.get(
        "/project/iw-ai-core/history?sort_by=id&sort_dir=asc"
    )
    
    # Assert — sort_by should not be in template context
    # After fix: the route handler ignores sort params entirely
    # The response should not contain sort_header <a> links
    assert 'sort_by=' not in response.text
    assert 'sort_dir=' not in response.text
    # Should contain client-side sortTable JS instead
    assert 'sortTable' in response.text
```

## Acceptance Criteria

### AC1: Client-side sorting works

```
Given the history page is loaded with items
When a column header is clicked
Then items are sorted instantly client-side (no page reload)
And a chevron icon indicates sort direction
And clicking again reverses the sort order
```

### AC2: Sorting matches batches page pattern

```
Given the history page table
When inspecting the HTML
Then each <tr> has data-sort-* attributes for all sortable columns
And each <th> has onclick="sortTable('key')"
And an inline <script> contains the sortTable() function
```

### AC3: No server-side sort interaction

```
Given the history page backend route
When the page is requested
Then sort_by and sort_dir query parameters are not processed
And no SQL ORDER BY is applied based on sort params
And _SORT_COLUMNS/_ALLOWED_SORT_BY constants are removed
```

### AC4: Pagination removed

```
Given the history page
When loaded with any number of items
Then all matching items are displayed (no pagination)
And no pagination UI is rendered
```

### AC5: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing test passes
```

## Regression Prevention

- Unit test verifying history response contains `sortTable` JS and no `sort_by=` links
- Unit test verifying `_history_items()` signature has no sort parameters
- Integration test verifying all items are returned (no pagination slicing)

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- Reproducing test: Test that history endpoint response contains `sortTable` JS function and does NOT contain `<a href="?sort_by=...">` links
- Unit tests: Verify `_history_items()` returns all items without sort/pagination params
- Integration tests: Verify history page renders all completed/failed items with `data-sort-*` attributes

## Notes

- The batches page (`batches.html:106-154`) is the reference implementation for the sorting pattern
- Removing pagination simplifies the template significantly — no more page links carrying sort/filter state
- The filter form (type, status, date range) remains server-side (requires DB query) — only sorting moves client-side
- Duration sort was also buggy in the old implementation (sorted by `completed_at` instead of actual duration) — client-side sorting with `data-sort-duration` fixes this automatically
