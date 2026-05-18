# I-00092 S12 Browser Verification Report

## Environment
- **Base URL used**: `http://localhost:9958` (from `$IW_BROWSER_BASE_URL`)
- **E2E user**: `e2e@iw.ai` / `iw-ai-core`

## V0: Pre-flight Page Sanity

**Status**: FAIL (pre-existing structural issue, does NOT block the filter-chip verifications)

**Finding**: The auto-merge page (`/project/iw-ai-core/auto-merge`) contains `hx-target="#auto-merge-status-chip"` referencing an element ID that does not exist in the DOM. The page has `id="auto-merge-chip-header"` but no `id="auto-merge-status-chip"`. This is a pre-existing dangling DOM reference unrelated to the filter-chip highlighting bug under test.

**Impact**: Does not affect the filter chip functionality. The htmx fragment loader for `auto-merge-status-chip` on the main page is separate from the `auto-merge-events` fragment tested in V1–V5.

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | fail | code_defect | — | Dangling `hx-target="#auto-merge-status-chip"` on main auto-merge page (pre-existing) |
| V1 | Default 'all' chip is highlighted | pass | null | `I-00092_v1_all_active.png` | `all` chip carries `bg-primary text-primary-foreground border-primary` |
| V2 | Click 'resolved' activates only that chip | pass | null | `I-00092_v2_resolved_active.png` | `resolved` chip has `bg-primary` + `title="merge_auto_resolved"` + `aria-pressed="true"`; no other chip has `bg-primary` |
| V3 | Click 'all' returns to default view | pass | null | `I-00092_v3_back_to_all.png` | After navigating to `/events` (no type param), `all` chip is active again |
| V4 | Tooltip shows event_type | pass | null | `I-00092_v4_tooltip.png` | Every chip has `title="<event_type>"` or `title="all event types"`; verified via curl HTML inspection |
| V5 | No regressions | pass | null | `I-00092_v5_no_regressions.png` | Queue page loads without console errors; verdict rollup and token cost rollup render correctly on auto-merge page |

## Console / Network Errors

**None observed.** No console error logs were produced during any page load or htmx fragment swap.

## Dangling DOM References Found

- `/project/iw-ai-core/auto-merge`: `hx-target="#auto-merge-status-chip"` — this element ID does not exist in the page. (Pre-existing structural bug, separate from the filter-chip issue under test.)
- `/project/iw-ai-core/queue`: no dangling references.

## Screenshots Captured

- `ai-dev/active/I-00092/evidences/post/I-00092_v1_all_active.png` — V1: 'all' chip highlighted on load
- `ai-dev/active/I-00092/evidences/post/I-00092_v2_resolved_active.png` — V2: 'resolved' chip highlighted with `type=merge_auto_resolved`
- `ai-dev/active/I-00092/evidences/post/I-00092_v3_back_to_all.png` — V3: 'all' chip active after returning to no-filter view
- `ai-dev/active/I-00092/evidences/post/I-00092_v4_tooltip.png` — V4: chip tooltips visible (HTML verified: all chips have correct `title` attributes)
- `ai-dev/active/I-00092/evidences/post/I-00092_v5_no_regressions.png` — V5: queue page renders cleanly, no errors

## Root Cause

**V0**: `dashboard/templates/pages/auto_merge.html` (or the fragment it includes) references `hx-target="#auto-merge-status-chip"` but the corresponding `id="auto-merge-status-chip"` element is not present in the DOM. The page defines `id="auto-merge-chip-header"` instead. This is a pre-existing structural bug unrelated to the I-00092 filter-chip fix.

**Filter-chip fix (V1–V4)**: The fix in `auto_merge_events_table.html` correctly compares `type_filter` (the raw URL value like `merge_auto_resolved`) against `mapped` (the tuple value), not `key`. All three acceptance criteria (AC1, AC2, AC3) are satisfied: the active chip is highlighted, `all` is active by default, and all chips carry correct `title` and `aria-pressed` attributes.

## Summary

The I-00092 fix is **working correctly**. The filter chips now:
1. Highlight the active filter (`bg-primary`) when a type is selected
2. Show `aria-pressed="true"` on the active chip and `"false"` on others
3. Display `title="<event_type>"` tooltips on all chips for discoverability

The V0 finding is a separate pre-existing issue: a dangling `hx-target="#auto-merge-status-chip"` reference on the main auto-merge page. This does not affect the filter chip functionality and should be filed as a separate issue.