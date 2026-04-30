# Browser Verification Prompt: I-00054-S11-BrowserVerification

**Work Item**: I-00054 -- Coverage Page Toggle Label Does Not Update on Expand/Collapse
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable to this step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use `$IW_BROWSER_BASE_URL`. The port is allocated per-worktree.

Do NOT run: `make dev`, `make e2e-up`, `docker compose`, `playwright install`, `agent-browser`, or `chromium.launch()`.

## Input Files

- `ai-dev/active/I-00054/I-00054_Issue_Design.md` — Design document
- `dashboard/templates/pages/system/coverage.html` — Modified template (read to understand the toggle logic)

## Output Files

- `ai-dev/active/I-00054/reports/I-00054_S11_BrowserVerification_Report.md` — Mandatory report
- `ai-dev/active/I-00054/evidences/post/` — Screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/system/coverage"
```

No login required — the coverage page is unauthenticated in the IW Core dashboard.

Rules for interacting with the page:
1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read current element IDs. Do not reuse refs from a previous page state.
2. Wait for htmx swaps to settle (1-2 seconds) before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00054/evidences/post/` with descriptive filenames.

## Verification Steps

### V1: Expand — label changes to "click to collapse"

1. Navigate to `$IW_BROWSER_BASE_URL/system/coverage`.
2. Take a snapshot to identify the first package row (e.g. a button labelled "dashboard ... click to expand").
3. Verify the initial label reads **"click to expand"** — this is the pre-click baseline.
4. Click the first package row to trigger the htmx expand.
5. Wait ~1 second for the htmx swap to complete, then take a new snapshot.
6. **Verify**: the label cell for that package now reads **"click to collapse"** (not "click to expand"). The file-level detail rows are visible below the package row.
7. **Screenshot**: `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00054/evidences/post/I-00054_v1_expand_label.png`

### V2: Collapse — label returns to "click to expand" and detail rows disappear

1. Continuing from V1 (row is expanded, label reads "click to collapse").
2. Click the same package row again to trigger the collapse.
3. Wait ~0.5 seconds, then take a new snapshot.
4. **Verify**: the label cell for that package now reads **"click to expand"** again. The file-level detail rows are NO LONGER visible below the package row.
5. **Screenshot**: `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00054/evidences/post/I-00054_v2_collapse_label.png`

### V3: Re-expand — toggle works a second time

1. Continuing from V2 (row is collapsed, label reads "click to expand").
2. Click the same row again.
3. Wait ~1 second, then take a new snapshot.
4. **Verify**: the label reads **"click to collapse"** again, and file detail rows are visible. This confirms the toggle is stateful and not a one-shot.
5. **Screenshot**: `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00054/evidences/post/I-00054_v3_re_expand.png`

### V4: No Regressions — other rows are independent

1. From the current page state (one row is expanded).
2. Take a snapshot to identify a second package row (e.g. "orch" or "executor").
3. **Verify**: the second row's label still reads **"click to expand"** — expanding one row must not affect other rows' labels or state.
4. Click the second row to expand it.
5. **Verify**: the second row now shows "click to collapse" and its own file details, while the first row retains its current state (expanded, showing "click to collapse").
6. **Screenshot**: `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00054/evidences/post/I-00054_v4_no_regressions.png`

### V5: No Console Errors

1. After all V1–V4 interactions, verify no JavaScript console errors appeared.
2. Revisit the page navigation (sidebar links) to confirm adjacent pages still load without errors.
3. **Screenshot**: `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00054/evidences/post/I-00054_v5_no_console_errors.png`

## Pass Criteria

All V1–V5 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail`.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — label text wrong, toggle doesn't work, console error. Use a normal `--reason`.
- **ENV_DATA_MISSING** — coverage page shows "No coverage data yet" (no `.coverage` file in the worktree). Prefix reason with `ENV_DATA_MISSING:`.

## Report

After verification, write `ai-dev/active/I-00054/reports/I-00054_S11_BrowserVerification_Report.md` containing:

- Pass/fail table with one row per V1–V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found with `file:line` references.
- List of screenshots captured (relative paths under `evidences/post/`).
- **No regressions observed** subsection covering V4–V5.

Then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00054/reports/I-00054_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00054/reports/I-00054_S11_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00054",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Expand — label changes to click to collapse", "status": "pass|fail", "screenshot": "evidences/post/I-00054_v1_expand_label.png", "notes": ""},
    {"id": "V2", "name": "Collapse — label returns to click to expand", "status": "pass|fail", "screenshot": "evidences/post/I-00054_v2_collapse_label.png", "notes": ""},
    {"id": "V3", "name": "Re-expand — toggle works a second time", "status": "pass|fail", "screenshot": "evidences/post/I-00054_v3_re_expand.png", "notes": ""},
    {"id": "V4", "name": "No regressions — other rows independent", "status": "pass|fail", "screenshot": "evidences/post/I-00054_v4_no_regressions.png", "notes": ""},
    {"id": "V5", "name": "No console errors", "status": "pass|fail", "screenshot": "evidences/post/I-00054_v5_no_console_errors.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
