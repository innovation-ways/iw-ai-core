# Browser Verification Prompt: F-00069-S13-BrowserVerification

**Work Item**: F-00069 -- Test Execution, Coverage Gate, Reports, and Coverage Dashboard View
**Step**: S13
**Agent**: qv-browser

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Do NOT run `make dev`, `make e2e-up`, or any `docker compose` command. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/F-00069/F-00069_Feature_Design.md`
- `dashboard/templates/pages/system/coverage.html`
- `dashboard/templates/fragments/coverage_files.html`
- `dashboard/templates/base.html` (nav addition)
- `dashboard/routers/coverage.py`
- `dashboard/services/coverage_service.py`

## Output Files

- `ai-dev/active/F-00069/reports/F-00069_S13_BrowserVerification_Report.md`
- `ai-dev/active/F-00069/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

(If the dashboard requires login in this stack, snapshot for fields and fill `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`. The current iw-ai-core dashboard does not require auth, but follow the snapshot-then-fill pattern if the login form appears.)

## E2E DB seed data

This feature does not require historical seed data — the coverage page reads `tests/output/coverage/coverage.json` from the worktree filesystem. Before V1, ensure that file exists by running the suite inside the e2e dashboard container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec dashboard \
  uv run pytest tests/unit -q
```

If the container path or service name differs, fall back to the host-side `make test-unit` ONLY if the host venv writes `tests/output/coverage/coverage.json` to a path the dashboard container can read. If neither works, call `iw step-fail` with `ENV_DATA_MISSING:` prefix.

## Verification Steps

### V1: Coverage page renders with data

1. Navigate to `$IW_BROWSER_BASE_URL/system/coverage`.
2. Wait for page load.
3. **Verify:**
   - Header card visible with "Overall Lines" cell showing a percentage.
   - "Threshold" cell visible with the `fail_under` value (a non-negative integer + "%").
   - Per-package table renders at least one row.
   - Each package row shows a colored badge with text GREEN, AMBER, or RED.
   - "Test Coverage" appears in the System nav (left sidebar).
   - No console errors.
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/F-00069/evidences/post/F-00069_v1_coverage_page.png`.

### V2: Drill-down via htmx

1. Already on `/system/coverage`.
2. `playwright-cli snapshot` to find the package row ref for `orch`.
3. `playwright-cli click <orch-row-ref>` — this should trigger `hx-get="/system/coverage/files/orch"` and swap the file table into the row below.
4. **Verify:**
   - File-level table appears under the orch row with one or more `orch/` files listed.
   - URL did NOT change (htmx swap, not navigation).
   - No console errors.
5. **Screenshot:** save as `F-00069_v2_drill_down.png`.

### V3: Empty state when coverage.json absent

1. Inside the dashboard container, remove the coverage artefact:
   ```bash
   docker compose -p "$COMPOSE_PROJECT_NAME" exec dashboard \
     rm -f tests/output/coverage/coverage.json
   ```
2. Navigate to `$IW_BROWSER_BASE_URL/system/coverage` (force reload).
3. **Verify:**
   - HTTP 200.
   - Empty-state card visible with message containing "No coverage data" and the `make test-unit` hint.
   - No package rows.
   - No console errors.
4. **Screenshot:** save as `F-00069_v3_empty_state.png`.
5. Restore the file by re-running the suite inside the container so subsequent verifications can run if needed.

### V4: Nav entry visible from another page

1. Navigate to `$IW_BROWSER_BASE_URL/system/status`.
2. **Verify:** the System sidebar contains a "Test Coverage" link with `href="/system/coverage"` between "System Status" and "All Active Work".
3. Click it; it should navigate to `/system/coverage`.
4. **Screenshot:** save as `F-00069_v4_nav_entry.png` (taken from the status page showing the nav).

### V5: No Regressions

1. Click through these adjacent System pages and verify they still render:
   - `/system/status`
   - `/system/worktrees`
   - `/system/all-active`
   - `/system/config`
2. Watch for new console errors on any of them.
3. **Screenshot:** save as `F-00069_v5_no_regressions.png` (any one of the pages with the nav visible).

## Pass Criteria

All V1–V5 must pass. Empty-state V3 is the most likely to need fixture coordination — if the file removal step fails, classify the failure as `ENV_DATA_MISSING:` rather than a code defect.

## Report

Write `ai-dev/active/F-00069/reports/F-00069_S13_BrowserVerification_Report.md` with:
- Pass/fail table (one row per V1–V5).
- The exact `$IW_BROWSER_BASE_URL` used.
- Screenshot list.
- "No regressions observed" subsection.

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00069/reports/F-00069_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00069/reports/F-00069_S13_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "F-00069",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "Coverage page renders with data", "status": "pass|fail", "screenshot": "evidences/post/F-00069_v1_coverage_page.png", "notes": ""},
    {"id": "V2", "name": "Drill-down via htmx", "status": "pass|fail", "screenshot": "evidences/post/F-00069_v2_drill_down.png", "notes": ""},
    {"id": "V3", "name": "Empty state", "status": "pass|fail", "screenshot": "evidences/post/F-00069_v3_empty_state.png", "notes": ""},
    {"id": "V4", "name": "Nav entry", "status": "pass|fail", "screenshot": "evidences/post/F-00069_v4_nav_entry.png", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "screenshot": "evidences/post/F-00069_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
