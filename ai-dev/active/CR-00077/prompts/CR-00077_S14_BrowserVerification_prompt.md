# Browser Verification Prompt: CR-00077-S14-BrowserVerification

**Work Item**: CR-00077 -- Overlap details popup (read-only)
**Step**: S14
**Agent**: qv-browser

---

## ⛔ Docker is off-limits
(Standard policy. The orchestrator's E2E stack is already running — do NOT touch docker compose.)

## ⛔ Migrations: agents generate, daemon applies
This CR adds no migrations.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. Use these env vars:

- **Base URL:** `$IW_BROWSER_BASE_URL`
- **E2E creds:** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
- **Item / step ids:** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or routes. Use `playwright-cli` exclusively. The seed DB is `pg_dump`-restored from production — so BATCH-00127 with its 5 Held items SHOULD be present at execution time. If it is not, navigate via the UI to find any other Held item in any batch.

## Input Files

- `ai-dev/active/CR-00077/CR-00077_CR_Design.md`
- `dashboard/routers/batches.py`
- `dashboard/templates/fragments/batch_overlap_modal.html`
- `dashboard/templates/fragments/batch_items_rows.html`
- `dashboard/templates/pages/project/batch_detail.html`
- `dashboard/static/styles.css`

## Output Files

- `ai-dev/active/CR-00077/reports/CR-00077_S14_BrowserVerification_Report.md`
- `ai-dev/active/CR-00077/evidences/post/` — screenshots.

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the dashboard requires auth in the e2e stack, snapshot, fill, click. (The local dev dashboard typically does not — match what the snapshot shows.)

## Verification Steps

### V1: Trigger pill opens the modal on the batch Items tab

1. Navigate via the UI: from the home page, click into **IW AI Core Platform**, then click **Batches**, then click the most recent batch that has at least one Held item (look for a row with status pill `pending` and a warning-colored cell saying `Held: overlaps with …`). If BATCH-00127 is present in the seed, prefer it.
2. Confirm you are on the `?tab=items` view.
3. Snapshot the page; locate the `Held: overlaps with …` pill — it MUST be inside a `<button>` element (not a plain `<span>`).
4. Click the pill button.
5. **Verify:** A modal appears (visible `[role="dialog"]`), title is `Overlap details — <item-id>` matching the row's item id, and the body shows at least one section with a link to another work item plus a `<ul>` of file globs. No `+N` text in the modal body.
6. **Screenshot:** `ai-dev/active/CR-00077/evidences/post/CR-00077_v1_modal_open.png`.

### V2: Files render verbatim (no truncation)

1. While the modal is still open from V1, count the rendered `<li>` items inside the modal body.
2. Compare against the trigger pill's hover `title` attribute (read it from the snapshot just before clicking — it lists all conflicting globs in a `Conflicting globs: <a, b, c>` segment) — every glob in the title must appear as its own `<li>` in the modal.
3. **Verify:** The modal contains every glob from the tooltip. No file glob is missing. No `+N` ellipsis in the modal.
4. **Screenshot:** `ai-dev/active/CR-00077/evidences/post/CR-00077_v2_full_globs.png`.

### V3: Esc closes the modal

1. With the modal open, send the Escape key via `playwright-cli press Escape` (or the equivalent).
2. Snapshot the page.
3. **Verify:** The modal is gone (no `[role="dialog"]` in the snapshot); `#overlap-modal-root` is empty or absent of children.
4. **Screenshot:** `ai-dev/active/CR-00077/evidences/post/CR-00077_v3_esc_closes.png`.

### V4: Backdrop / × close paths

1. Re-open the modal by clicking the pill again.
2. Click the backdrop (the area outside the white container).
3. **Verify:** Modal closes.
4. Re-open the modal. Click the `×` button in the header.
5. **Verify:** Modal closes.
6. **Screenshot:** `ai-dev/active/CR-00077/evidences/post/CR-00077_v4_close_paths.png`.

### V5: No Regressions

1. Visit the Items tab of any batch that has no held items — assert no `[role="dialog"]` ever appears unexpectedly, no JS console errors during the page load.
2. Visit a held item's detail page — assert the page loads normally.
3. **Verify:** No new console errors in `.playwright-cli/console-*.log`.
4. **Screenshot:** `ai-dev/active/CR-00077/evidences/post/CR-00077_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass.

## Report + step-done/step-fail

Standard contract — see `ai-dev/templates/QVBrowser_Prompt_Template.md`.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "CR-00077",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<concrete URL>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Trigger opens modal — Items tab", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Full glob list rendered", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Esc closes modal", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Backdrop and × close paths", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
