# Browser Verification Prompt: CR-00065-S11-BrowserVerification

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has already started an isolated E2E stack. Do NOT start, stop, or rebuild any services.

**Base URL:** `$IW_BROWSER_BASE_URL`
**Credentials:** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step:** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode any ports or route paths. Navigate via the UI.

## Input Files

- `ai-dev/active/CR-00065/CR-00065_CR_Design.md` — Design document
- `dashboard/templates/fragments/item_steps_table.html`
- `dashboard/templates/fragments/session_log_popup_content.html`
- `dashboard/routers/items.py`

## Output Files

- `ai-dev/active/CR-00065/reports/CR-00065_S11_BrowserVerification_Report.md`
- `ai-dev/active/CR-00065/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in with `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`.

## E2E DB Seed Data

The E2E DB is seeded from production. It should contain items with completed steps (including pi runs from recent work). If not, add a fixture file `ai-dev/active/CR-00065/e2e_fixtures/001_session_log_seed.py` that inserts a `WorkItem` + `WorkflowStep` + `StepRun` with `cli_tool="pi"`, `session_file=<a real path from ~/.pi/agent/sessions/>`, `log_content="sample log"`, and another with `cli_tool="claude"`, `log_content="claude log output"`.

After writing the fixture:
```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

## Verification Steps

### V0: Pre-flight page sanity (built-in — do not modify)

### V1: Logs column visible in step table

1. Navigate to the History page and open any item with completed steps.
2. Scroll to the step pipeline table.
3. **Verify**: a "Logs" column header is visible immediately to the right of the "Status" column.
4. **Verify**: each row with at least one run shows a log icon button; pending rows show "—".
5. **Screenshot**: `ai-dev/active/CR-00065/evidences/post/CR-00065_v1_logs_column.png`.

### V2: Popup opens and shows content for a completed step

1. Click the Logs icon button on any completed step row.
2. **Verify**: a modal popup opens with the title "Agent Session Log".
3. **Verify**: the popup body contains recognisable content (not empty, not raw JSON, not a Python traceback).
4. **Verify**: the run number and CLI tool badge are visible in the popup header area.
5. **Screenshot**: `ai-dev/active/CR-00065/evidences/post/CR-00065_v2_popup_open.png`.

### V3: Pi run shows structured rendering (if available)

1. Find an item that ran with the Pi runtime (look for "Pi" in the CLI column).
2. Click the Logs button for a Pi step.
3. **Verify**: the popup shows formatted content — not raw JSONL, not empty. Look for assistant text, tool call summaries, or "context compacted" dividers.
4. **Verify**: thinking blocks (if present) show as collapsed `<details>` elements.
5. **Screenshot**: `ai-dev/active/CR-00065/evidences/post/CR-00065_v3_pi_session.png`.

### V4: Popup closes correctly

1. With the popup open, press Escape.
2. **Verify**: the modal disappears.
3. Open the popup again and click outside the modal panel (on the dark overlay).
4. **Verify**: the modal disappears again.
5. **Screenshot**: `ai-dev/active/CR-00065/evidences/post/CR-00065_v4_modal_closed.png`.

### V5: No Regressions

1. Navigate to the Queue page, then to Batches, then to any item detail. Verify these pages load without JS errors.
2. Open the Logs tab (existing tab) on an item and verify it still renders correctly.
3. Check the browser console for unhandled errors on all visited pages.
4. **Screenshot**: `ai-dev/active/CR-00065/evidences/post/CR-00065_v5_no_regressions.png`.

## Pass Criteria

All V1–V5 must pass. Any unhandled JS error or missing element constitutes a FAIL.

## Report

Write `ai-dev/active/CR-00065/reports/CR-00065_S11_BrowserVerification_Report.md`.

```bash
# On pass
uv run iw step-done CR-00065 --step S11 \
  --report ai-dev/active/CR-00065/reports/CR-00065_S11_BrowserVerification_Report.md

# On failure
uv run iw step-fail CR-00065 --step S11 \
  --reason "<reason>" \
  --report ai-dev/active/CR-00065/reports/CR-00065_S11_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "CR-00065",
  "overall_status": "pass|fail",
  "overall_failure_class": null,
  "base_url_used": "",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Logs column visible", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Popup opens with content", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Pi session structured rendering", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Popup closes correctly", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
