# I003_S02_CodeReview Report

## Result
```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00003",
  "completion_status": "NEEDS_FIX",
  "findings_count": 5,
  "critical_count": 0,
  "high_count": 2,
  "medium_count": 2,
  "low_count": 1
}
```

## Summary

The client-side sorting implementation is functionally correct and consistent with the `batches.html` pattern. The JavaScript sort logic, data attributes, empty-row handling, and sort indicators are all implemented properly. However, the removal of pagination without adjusting the backend page size creates a silent regression: projects with more than 20 history items will silently truncate output with no UI affordance to see the rest. The backend route also retains dead sort/pagination code that now has no effect.

---

## Findings

### [HIGH] Pagination Removed but Backend Still Paginates — Items Beyond Page 20 Unreachable

- **File**: `dashboard/templates/pages/project/history.html`
- **Lines**: (pagination block removed — was lines 139–179 in original)
- **Description**: The template previously had a full pagination widget. It was removed as part of the client-side sort migration. However, the backend route (`dashboard/routers/project_pages.py`, lines 204–205) still slices results to `_HISTORY_PAGE_SIZE = 20` items per page, and the template renders with `page=1` by default. There is no way for a user to request page 2 or beyond. For any project with more than 20 completed/failed work items, the excess items are silently dropped from the view. The `total` count displayed (e.g. "47 items") will correctly show the full count, which creates a confusing discrepancy between the count and the visible rows.
- **Recommendation**: Either (a) remove server-side pagination so `_history_items()` returns all matching rows (simplest fix given client-side sorting now owns the data), or (b) restore the pagination widget in the template. Option (a) is preferred: replace the `all_rows[offset : offset + _HISTORY_PAGE_SIZE]` slice with returning all `all_rows` directly, and remove the `page`/`total_pages`/`page_size` parameters from the route response.

### [HIGH] Backend Route Retains Dead Sort and Pagination Code

- **File**: `dashboard/routers/project_pages.py`
- **Lines**: 31, 38–46, 149–205, 258–259, 274–296
- **Description**: The backend still accepts `sort_by` and `sort_dir` query parameters, validates them against `_ALLOWED_SORT_BY`/`_ALLOWED_SORT_DIR`, applies `ORDER BY` to the SQL query, performs page slicing with `_HISTORY_PAGE_SIZE`, and passes `sort_by`, `sort_dir`, `page`, `total_pages`, and `page_size` back to the template — none of which the template uses anymore. The sort constants `_SORT_COLUMNS`, `_ALLOWED_SORT_BY`, `_ALLOWED_SORT_DIR`, `nulls_first`, `nulls_last`, and the dynamic `ORDER BY` block are all dead code. This is a maintenance hazard: future editors may assume sort parameters affect the UI.
- **Recommendation**: Clean up `project_pages.py` to remove the dead sort/pagination logic. Remove `sort_by`, `sort_dir`, `page`, `sort_by`/`sort_dir` query params from the route signature, remove `_SORT_COLUMNS`, `_ALLOWED_SORT_BY`, `_ALLOWED_SORT_DIR`, the dynamic `ORDER BY` block, the page slice, `nulls_first`/`nulls_last` imports, and the corresponding template context keys. Update `_history_items()` to simply return all rows in a consistent default order (e.g. `created_at DESC`).

### [MEDIUM] Sort by `created_at` Uses Attribute Key with Underscore — Verify Browser Compatibility

- **File**: `dashboard/templates/pages/project/history.html`
- **Lines**: 108, 163
- **Description**: The data attribute is `data-sort-created_at` (with underscore). In HTML5, custom `data-*` attribute names are valid with underscores and `getAttribute('data-sort-created_at')` works correctly in all modern browsers. However, this deviates slightly from the batches.html pattern which uses only alphanumeric keys (`id`, `status`, `items`, `progress`, `created`, `duration`). Notably, batches.html uses `data-sort-created` (no underscore, shorter key) for its created column, while history.html uses `data-sort-created_at`. This inconsistency is minor but could confuse future contributors about the naming convention.
- **Recommendation**: Rename the sort key from `created_at` to `created` to be consistent with the batches page pattern. Change the column definition from `("created_at", "Date")` to `("created", "Date")`, update the `data-sort-created_at` attribute to `data-sort-created`, and update `onclick="sortTable('created_at')"` to `onclick="sortTable('created')"`. No backend changes needed since the sort key is only used in the JS.

### [MEDIUM] Results Count Loses Page Context — User Cannot Tell Visible vs. Total

- **File**: `dashboard/templates/pages/project/history.html`
- **Lines**: 67–69
- **Description**: The original template showed "Showing 1–20 of 47 items" which communicated that pagination was in effect. The new template shows "47 items" while only displaying 20 rows (due to the backend still paginating). Even if pagination is fully removed from the backend (see HIGH finding above), changing the count to just "N items" removes useful context. If many items are returned after removing pagination, the bare count gives no indication of how many are visible.
- **Recommendation**: If pagination is removed from the backend, the count "N items" is accurate and appropriate (all items are shown). This finding resolves itself once the HIGH finding about backend pagination is addressed. If pagination is retained, restore the "Showing X–Y of N items" format.

### [LOW] Accessibility: `aria-sort` Attribute Removed from Column Headers

- **File**: `dashboard/templates/pages/project/history.html`
- **Lines**: 85–96
- **Description**: The original `sort_header` macro included `aria-sort` on each `<th>` element (`aria-sort="ascending"`, `aria-sort="descending"`, or `aria-sort="none"`). The new implementation omits `aria-sort` entirely. Screen readers use this attribute to announce sort state to users. The sort icon is visual-only.
- **Recommendation**: Update the `sortTable()` JavaScript function to set `aria-sort` on the active column header after each sort operation. For the active column: set `aria-sort="ascending"` or `aria-sort="descending"`. For all other columns: remove `aria-sort` or set it to `"none"`. This is a small addition to the existing icon-update loop in the script.

---

## Verified Correct

The following aspects were verified and are correct:

- **Sort logic**: `localeCompare` for string columns, `parseFloat` for `duration` — correct. ISO 8601 datetime strings sort correctly with string comparison.
- **Duration sentinel**: Using `-1` for null durations places items without duration at the top when sorting ascending (a reasonable default).
- **Empty row handling**: `tr:not(.empty-row)` correctly excludes the empty state row from sorting operations.
- **XSS safety**: Jinja2 HTML auto-escaping is active for `.html` templates (FastAPI's `Jinja2Templates` enables it by default). All `data-sort-*` attribute values are HTML-entity-escaped.
- **Sort toggle**: Clicking the same column toggles direction; clicking a new column resets to `asc`. This matches `batches.html` exactly.
- **Sort icons**: Opacity and rotation logic correctly indicates active sort column and direction, consistent with `batches.html`.
- **Clear link**: `href="?"` correctly clears all filters. The old link preserved sort params that are no longer relevant.
- **`onclick` navigation**: URL construction for item detail links is unchanged and correct.
- **Pattern consistency**: The overall structure (IIFE scope, `window.sortTable`, selector queries, DOM append pattern) is identical to `batches.html`.
