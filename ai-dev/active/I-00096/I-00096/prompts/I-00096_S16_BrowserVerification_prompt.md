# Browser Verification Prompt: I-00096-S16-BrowserVerification

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step**: S16
**Agent**: qv-browser

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Environment

Isolated E2E stack already up.

- `$IW_BROWSER_BASE_URL`
- `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
- `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or run `make dev` / `docker compose …` /
`playwright install` / `agent-browser` / direct `chromium.launch()`.

## Input Files

- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- All files in S01/S03/S05 `files_changed`

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S16_BrowserVerification_Report.md`
- `ai-dev/active/I-00096/evidences/post/`

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in if needed.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

Standard auto-prepended check.

### V1: Exactly one chip on /auto-merge

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge`.
2. `playwright-cli snapshot`.
3. **Verify** the snapshot contains exactly ONE
   `auto-merge-status-chip` element (or equivalent role/label
   indicator). Also verify via curl:

   ```bash
   curl -s "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge" | grep -c 'id="auto-merge-status-chip"'
   # Must print 1
   ```

4. **Screenshot:** `ai-dev/active/I-00096/evidences/post/I-00096_v1_one_chip.png`.

### V2: Topbar chip appears on other project pages

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/queue`.
2. `playwright-cli snapshot`.
3. **Verify** the snapshot shows the compact auto-merge chip in the
   topbar.
4. **Screenshot:** `ai-dev/active/I-00096/evidences/post/I-00096_v2_topbar_other_page.png`.

### V3: Default events view excludes non-auto-merge

1. Navigate back to `/auto-merge`.
2. Scroll through the visible events. They should be uniformly
   `auto_merge_*` or `merge_auto_*` types — no `step_launched`,
   `step_completed`, `item_approved`, `fix_cycle_*`, `step_crashed`.
3. **Verify** via curl:

   ```bash
   curl -s "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/events?page=0&page_size=50" | grep -E 'step_launched|step_completed|item_approved|fix_cycle_|step_crashed' | head
   # Should be empty
   ```

4. **Screenshot:** `ai-dev/active/I-00096/evidences/post/I-00096_v3_default_excludes.png`.

### V4: Show-all toggle reveals non-auto-merge events

1. Click the "Show all daemon events" toggle.
2. Wait for the swap.
3. **Verify** the table now contains rows with event_types like
   `step_launched`, `step_completed`, etc.
4. **Verify** the button text flipped to "Auto-merge events only".
5. **Screenshot:** `ai-dev/active/I-00096/evidences/post/I-00096_v4_show_all.png`.

### V5: Filter + show-all + sort compose

1. With show-all active, click the `step_launched` filter chip (this
   row exists if/when previous incidents added it; otherwise click
   `all` and confirm sort still works).
2. **Verify** URL contains both `?type=step_launched` (or whatever
   filter) AND `&all=1`.
3. **Screenshot:** `ai-dev/active/I-00096/evidences/post/I-00096_v5_compose.png`.

### V6: Click "Auto-merge events only" returns to filtered view

1. Click the toggle (now labelled "Auto-merge events only").
2. **Verify** the table re-renders excluding non-auto-merge events.
3. **Screenshot:** `ai-dev/active/I-00096/evidences/post/I-00096_v6_back_to_default.png`.

### V7: No regressions

1. Verdict pills (`pending`/`correct`/…) on resolved-event rows still
   work (if any exist in seed).
2. `(view)` link still opens the modal.
3. No console errors throughout V1..V6.
4. **Screenshot:** `ai-dev/active/I-00096/evidences/post/I-00096_v7_no_regressions.png`.

## Pass Criteria

All V1..V7 pass.

- CODE_DEFECT: two chips render; default view still includes
  non-auto-merge; toggle button doesn't flip state.
- ENV_DATA_MISSING: no non-auto-merge events exist in the seed for V3
  to demonstrate (unlikely on a real worktree; add fixture if so).

## Report

Write
`ai-dev/active/I-00096/reports/I-00096_S16_BrowserVerification_Report.md`
with pass/fail table, base URL, screenshots, and "no regressions
observed" section. Call `iw step-done` or `iw step-fail` with
`--report`.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "I-00096",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Exactly one chip on /auto-merge", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Topbar chip on other pages", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Default view excludes non-auto-merge", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Show-all toggle reveals everything", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Filter + show-all + sort compose", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Toggle back returns to filtered view", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V7", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
