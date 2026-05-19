# Browser Verification Prompt: I-00094-S12-BrowserVerification

**Work Item**: I-00094 — Auto-merge htmx-only `<a>` tags render with text cursor and bad accessibility
**Step**: S12
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

- `ai-dev/active/I-00094/I-00094_Issue_Design.md`
- The three modified fragment templates

## Output Files

- `ai-dev/active/I-00094/reports/I-00094_S12_BrowserVerification_Report.md`
- `ai-dev/active/I-00094/evidences/post/`

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in if needed.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

Standard auto-prepended check.

### V1: Filter chips appear as buttons in the a11y tree

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge`.
2. Wait for the events fragment to load.
3. `playwright-cli snapshot`.
4. **Verify** in the snapshot YAML: each filter chip
   (`all`, `resolved`, …) appears as `button "<label>"` or
   `button "<label>" [ref=eNNN] [cursor=pointer]`, NOT as
   `generic "<label>"`.
5. **Screenshot:** `ai-dev/active/I-00094/evidences/post/I-00094_v1_chips_a11y.png`.

### V2: View link appears as button

1. Locate any event row's `(view)` element in the snapshot.
2. **Verify** it appears as `button "(view)"` not
   `cell "(view)"` / `generic "(view)"`.
3. **Screenshot:** `ai-dev/active/I-00094/evidences/post/I-00094_v2_view_a11y.png`.

### V3: Rollup window toggles appear as buttons

1. Locate the `7d` and `30d` elements.
2. **Verify** they appear as `button "7d"` and `button "30d"`.
3. **Screenshot:** `ai-dev/active/I-00094/evidences/post/I-00094_v3_toggles_a11y.png`.

### V4: Click behaviour still works

1. Click a filter chip (e.g. `resolved`).
2. **Verify** the events table re-renders filtered (or shows the
   empty-state message), proving htmx still triggers.
3. Click `(view)` on any row.
4. **Verify** the modal opens.
5. **Screenshot:** `ai-dev/active/I-00094/evidences/post/I-00094_v4_click_works.png`.

### V5: Keyboard accessibility

1. Use `playwright-cli press Tab` repeatedly from a known anchor; the
   filter chips, `(view)` actions, and rollup toggles should appear in
   the tab order with a visible focus indicator.
2. Press Enter on a focused chip; verify it activates the same as a
   click.
3. **Screenshot:** `ai-dev/active/I-00094/evidences/post/I-00094_v5_keyboard.png`.

### V6: No regressions

1. Navigate away (to `/queue`) and back; everything still renders.
2. No new console errors.
3. **Screenshot:** `ai-dev/active/I-00094/evidences/post/I-00094_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 pass.

- CODE_DEFECT: chip still appears as `generic` in the a11y tree;
  cursor still text; htmx no longer triggers on click.
- ENV_DATA_MISSING: e.g., no events at all in seed so V2 can't pick a
  row — unlikely.

## Report

Write `ai-dev/active/I-00094/reports/I-00094_S12_BrowserVerification_Report.md`
with pass/fail table, base URL, screenshots, and "no regressions
observed" section. Then `iw step-done` / `iw step-fail` with `--report`.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "qv-browser",
  "work_item": "I-00094",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Filter chips are buttons", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "View link is button", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Rollup toggles are buttons", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Clicks still work", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Keyboard accessibility", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
