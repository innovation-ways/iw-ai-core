# F-00014 S03 Frontend Report

## Summary

Completed all frontend implementation for F-00014 Phase 4 documentation polish. Implemented version diff viewer with selection UI, enhanced global docs search page, multi-select export functionality, broken links callout, and top-level Docs nav entry.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/docs_version_drawer.html` | Added version checkboxes with Alpine.js selection logic, Compare button, diff viewer container |
| `dashboard/templates/fragments/docs_diff.html` | Enhanced unified diff display with line-level styling (added/removed/context), truncation at 100 lines, close button |
| `dashboard/templates/docs_global.html` | Rebuilt with platform branding header, large search bar, filter pills (type/status/tier), project dropdown |
| `dashboard/templates/fragments/docs_global_results.html` | Added result count header, highlighted terms with `<mark>` conversion from `<b>` tags, project chips, proper type badges |
| `dashboard/templates/fragments/docs_broken_links.html` | Changed to orange color scheme per spec, added Re-check button |
| `dashboard/templates/docs_library.html` | Added Select mode toggle, floating action bar with Export Selected/Clear buttons, select mode state management |
| `dashboard/templates/fragments/docs_card.html` | Added per-card checkbox (hidden until select mode), per-card Export button, select mode visibility toggle via MutationObserver |
| `dashboard/templates/base.html` | Added Documentation section with Docs nav link (with active state for `/docs` paths) |
| `dashboard/templates/docs_detail.html` | Added broken-links-callout div (conditionally rendered when doc.broken_links is not None) |

## Test Results

- `make quality` — ruff check and format check passed; mypy showed 1 pre-existing error (missing yaml type stubs in `orch/doc_service.py:17`) unrelated to these changes
- All changes are Jinja2 templates (no Python code added)
- No new JavaScript frameworks introduced — using vanilla JS + Alpine.js (already in use)

## Implementation Details

### Version Diff Viewer
- Checkbox added to each version row with `x-data` tracking
- Compare button appears when exactly 2 versions selected (sorted)
- Diff fetched via `htmx.ajax()` with `GET /api/project/{id}/docs/{doc_id}/diff?v1=N&v2=M`
- Unified diff view with green additions, red deletions, blue hunk markers
- Truncation at 100 lines with "Show all" option
- Close button resets selection and clears diff viewer

### Global Search Page
- Full-width centered layout, max-w-4xl
- Large search input with 300ms debounce
- Filter pills for doc_type, status, tier + project dropdown
- Results grouped by project with count headers
- Search term highlighting (converts `<b>` from `ts_headline()` to `<mark>`)

### Multi-Select Export
- "Select" button toggles select mode (changes to "Cancel")
- Per-card checkboxes appear in select mode (via CSS/JS)
- Floating action bar shows count + Export Selected/Clear
- Export navigates to `/api/project/{id}/docs/export?doc_ids={joined}`
- Per-card Export button provides single-doc download

### Broken Links Callout
- Orange warning styling with Re-check button
- Shows broken links list with type, URL, status
- Green "All links valid" state when no broken links

## Notes

- The pre-existing mypy error about missing `types-PyYAML` stubs was present before these changes and is unrelated
- All interactive elements have proper `aria-*` attributes
- No breaking changes to existing functionality