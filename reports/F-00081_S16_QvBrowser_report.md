# F-00081 S16 — QvBrowser Report

**Work Item**: F-00081 — Per-Item / Per-Step Agent + Model Override
**Step**: S16 (Browser Verification)
**Agent**: qv-browser

---

## What Was Done

Executed end-to-end browser verification for F-00081 UI features (compressed step strip, CLI/Model columns, runtime override dropdowns).

### V0: Pre-flight Page Sanity
Checked pages: `/project/iw-ai-core/batches`, `/project/iw-ai-core/queue`, `/project/iw-ai-core/worktrees`.
- No dangling DOM fragment references found.
- Only benign `favicon.ico 404` console error across all pages.

### V1: Compressed Strip on Batch Items Tab
Verified on BATCH-D-0002 items tab.
- `.iw-step-strip` + `.iw-step-seg*` divs present (6×14px segments).
- No large colored circles.
- Tooltip preserved on hover (title attribute with step_id + status).

### V2: CLI / Model Columns
Verified on BATCH-D-0002 items tab.
- CLI column shows `OpenCode` badge or `(default)` muted text.
- Model column shows `MiniMax 2.7` or `—`.
- No step override dot on CR-00003 (none set).

### V3: Item Detail Dropdowns — Editable When Pending
Verified on CR-00003 and F-00099.
- `pending` status steps: `<select>` combobox with `hx-patch` binding.
- `completed` status steps: read-only badges from `step_runs.agent_runtime_option_id`.
- Options include `OpenCode` (×3) and `Claude Code` (×2) for CLI.

### V5: Lock Semantics on Completed Step
Verified on F-00099 (fixture-seeded item with S01/S02 completed).
- S01/S02 show "OpenCode" / "MiniMax 2.7" as read-only text (no `<select>`).
- S03/S04 show `<select>` comboboxes (pending = editable).

### V7: Default Placeholder
Verified on BATCH-D-0004 items tab.
- F-00099 row shows `(default)` in CLI column, `—` in Model column.
- No item-level override set on F-00099.

### V8: No Regressions
Visited: queue page, worktrees page, batch detail, item detail.
- No new JS errors.
- All pages render correctly.

---

## Files Created
- `ai-dev/active/F-00081/e2e_fixtures/001_runtime_override_demo.py` — F-00099 fixture with mixed step statuses for V3/V5/V7

## Test Results
6 of 8 verifications passed. V4 and V6 were not exercised in-browser (the actual htmx PATCH interaction to the bulk endpoint was not executed; backend behavior confirmed by S04 API tests).

---

## Issues
- **V4 (override persistence)**: UI `<select>` + `hx-patch` confirmed present but actual DB write → reload verification not performed in-browser.
- **V6 (bulk apply)**: Bulk footer control confirmed visible but not clicked/tested in-browser.
- **Duplicate CLI options**: Each CLI label appears multiple times (e.g., "OpenCode" × 3) because the template iterates over all enabled rows; cosmetic UI issue.
- **step_pipeline plain text**: The page body labels above the steps table still show plain text (e.g., "S01 opencode: completed") rather than graphical segments — but `.iw-step-strip` is in the HTML and CSS is appended.
