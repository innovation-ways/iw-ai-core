# Browser Verification Prompt: CR-00066-S10-BrowserVerification

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S10
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has already started an isolated E2E stack. Do NOT start or rebuild any services.

**Base URL:** `$IW_BROWSER_BASE_URL`
**Credentials:** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step:** `$IW_ITEM_ID` / `$IW_STEP_ID`

## Input Files

- `ai-dev/active/CR-00066/CR-00066_CR_Design.md`
- `dashboard/templates/fragments/item_steps_table.html`
- `dashboard/routers/items.py`

## Output Files

- `ai-dev/active/CR-00066/reports/CR-00066_S10_BrowserVerification_Report.md`
- `ai-dev/active/CR-00066/evidences/post/`

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in with `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`.

## E2E DB Seed Data

The E2E DB is seeded from production. To verify the progress bar, you need `StepRun` rows with `context_tokens_peak` set. If none exist, add a fixture:

`ai-dev/active/CR-00066/e2e_fixtures/001_context_tokens_seed.py`

Create a `WorkItem` + `WorkflowStep` + `StepRun` with:
- `cli_tool = "pi"`, `context_tokens_peak = 150000`, `context_tokens_last = 150000`
- `agent_runtime_option_id` pointing to a row with `context_window_tokens = 200000` (e.g. the MiniMax-M2.7 row)

And another run with `context_tokens_peak = 50000` (green zone).

After writing the fixture:
```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

## Verification Steps

### V0: Pre-flight page sanity (built-in — do not modify)

### V1: Context column header visible

1. Navigate to History and open any item with steps.
2. **Verify**: a "Context" column header is visible immediately right of "Logs" (which is right of "Status").
3. **Screenshot**: `ai-dev/active/CR-00066/evidences/post/CR-00066_v1_context_column.png`.

### V2: Green bar for low-usage step

1. Find (or seed) a step with `context_tokens_peak = 50000`, `context_window_tokens = 200000` (25% usage).
2. **Verify**: the Context cell shows "50K / 200K" and "25%" with a green bar.
3. **Screenshot**: `ai-dev/active/CR-00066/evidences/post/CR-00066_v2_green_bar.png`.

### V3: Yellow bar for elevated-usage step

1. Find (or seed) a step with `context_tokens_peak = 150000`, `context_window_tokens = 200000` (75% usage).
2. **Verify**: the Context cell shows "150K / 200K" and "75%" with a yellow/amber bar.
3. **Screenshot**: `ai-dev/active/CR-00066/evidences/post/CR-00066_v3_yellow_bar.png`.

### V4: Dash for pending/no-data steps

1. Find a step that is `pending` or has no `context_tokens_peak` data.
2. **Verify**: the Context cell shows "—".
3. **Screenshot**: `ai-dev/active/CR-00066/evidences/post/CR-00066_v4_dash_pending.png`.

### V5: No Regressions

1. Verify the Logs column (added by CR-00065) is still present and functional.
2. Verify no new JS/console errors on the item detail page.
3. **Screenshot**: `ai-dev/active/CR-00066/evidences/post/CR-00066_v5_no_regressions.png`.

## Pass Criteria

All V1–V5 must pass.

## Report + Result Contract

Write `ai-dev/active/CR-00066/reports/CR-00066_S10_BrowserVerification_Report.md`.

```bash
uv run iw step-done CR-00066 --step S10 \
  --report ai-dev/active/CR-00066/reports/CR-00066_S10_BrowserVerification_Report.md
# or fail:
uv run iw step-fail CR-00066 --step S10 \
  --reason "<reason>" \
  --report ai-dev/active/CR-00066/reports/CR-00066_S10_BrowserVerification_Report.md
```

```json
{
  "step": "S10",
  "agent": "qv-browser",
  "work_item": "CR-00066",
  "overall_status": "pass|fail",
  "overall_failure_class": null,
  "base_url_used": "",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Context column header visible", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Green bar for low-usage step", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Yellow bar for elevated-usage step", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Dash for pending/no-data steps", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
