# Browser Verification Prompt: F-00074-S13-BrowserVerification

**Work Item**: F-00074 — Keep-Alive Scheduler
**Step**: S13
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var. Do NOT run `make dev`, `docker compose`, `playwright install`, or `agent-browser`. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/F-00074/F-00074_Feature_Design.md`
- `dashboard/routers/keep_alive.py`
- `dashboard/templates/pages/system/keep_alive.html`
- `dashboard/templates/fragments/keep_alive_timeline.html`
- `dashboard/templates/fragments/keep_alive_slots.html`
- `dashboard/templates/fragments/keep_alive_runs.html`

## Output Files

- `ai-dev/active/F-00074/reports/F-00074_S13_BrowserVerification_Report.md`
- `ai-dev/active/F-00074/evidences/post/` — screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
playwright-cli snapshot
# Log in with E2E credentials
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

## E2E DB Seed Data

The E2E stack DB is seeded from production. If the `keep_alive_config` table exists but has no slots or runs, that is the expected empty state (production has none yet). The V1 and V2 verifications work with an empty state. V3 (runs table) requires at least one run row — add a fixture if needed:

```
ai-dev/active/F-00074/e2e_fixtures/001_f00074_keepalive_seed.py
```

```python
from sqlalchemy.orm import Session
from orch.db.models import KeepAliveConfig, KeepAliveSlot, KeepAliveRun
from datetime import datetime

def seed(db: Session) -> None:
    # Ensure config
    config = db.get(KeepAliveConfig, 1)
    if not config:
        config = KeepAliveConfig(id=1, model="claude-sonnet-4-6", window_duration_hours=5)
        db.add(config)
        db.flush()

    # Ensure one slot
    existing = db.query(KeepAliveSlot).filter_by(time_hhmm="10:02").first()
    if not existing:
        slot = KeepAliveSlot(time_hhmm="10:02", enabled=True, config_id=1)
        db.add(slot)
        db.flush()
        existing = slot

    # Ensure one run
    run_exists = db.query(KeepAliveRun).filter_by(slot_time="10:02").first()
    if not run_exists:
        db.add(KeepAliveRun(
            slot_id=existing.id,
            slot_time="10:02",
            fired_at=datetime(2026, 4, 30, 10, 2, 0),
            status="success",
        ))
    db.commit()
```

After writing the fixture, re-run the seed inside the `app` container:
```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

## Verification Steps

### V1: Keep-Alive page loads and nav entry is present

1. Navigate to `$IW_BROWSER_BASE_URL/system/keep-alive`.
2. Take a snapshot — verify the page title "Keep-Alive Scheduler" is present and the sidebar shows a "Keep-Alive" link in the System section.
3. **Verify:** page renders with no error (HTTP 200), config card visible (model dropdown, window-duration dropdown, Save Config button).
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00074/evidences/post/F-00074_v1_page_load.png`

### V2: Add a slot and verify timeline updates

1. Still on `$IW_BROWSER_BASE_URL/system/keep-alive`.
2. Snapshot to find the time-input field and "Add Slot" button.
3. Fill the time input with `"15:04"` and click Add Slot — this triggers `POST /api/keep-alive/slots` and should update the slot list and timeline via htmx without a full page reload.
4. **Verify:** a row for `"15:04"` appears in the slot table with an "Active" badge; the timeline bar shows at least one green block.
5. **Screenshot:** `ai-dev/active/F-00074/evidences/post/F-00074_v2_slot_added.png`

### V3: Toggle a slot and verify badge changes

1. Find the "Disable" button for the `"15:04"` (or the seeded `"10:02"`) slot row.
2. Click it — triggers `PATCH /api/keep-alive/slots/{id}/toggle`.
3. **Verify:** the badge on that row changes from "Active" to "Disabled" without a full page reload.
4. Click Enable to restore it.
5. **Verify:** badge returns to "Active".
6. **Screenshot:** `ai-dev/active/F-00074/evidences/post/F-00074_v3_slot_toggled.png`

### V4: Last 10 runs table visible

1. Scroll to the "Recent Executions" section.
2. **Verify:** if the seed fixture ran, at least one run row is visible with a timestamp, slot time, and status badge. If no seed was provided and the table is empty, verify the "No executions yet" empty state is shown.
3. **Screenshot:** `ai-dev/active/F-00074/evidences/post/F-00074_v4_runs_table.png`

### V5: Config save

1. Change the window-duration dropdown to "4 hours".
2. Click "Save Config".
3. **Verify:** the form responds (updated values reflected or success indication); no full page reload.
4. Change back to "5 hours" and save again to restore.
5. **Screenshot:** `ai-dev/active/F-00074/evidences/post/F-00074_v5_config_saved.png`

### V6: No Regressions

1. Navigate to `/system/status` — verify it still renders correctly.
2. Navigate to `/system/coverage` — verify it still renders correctly.
3. Check browser console for new errors on any page visited during V1–V5.
4. **Screenshot:** `ai-dev/active/F-00074/evidences/post/F-00074_v6_no_regressions.png`

## Pass Criteria

All V1–V6 must pass. Any failure or ambiguous result requires `iw step-fail`.

Classify failures:
- **CODE DEFECT**: HTTP error, Jinja exception, broken htmx swap, missing element.
- **ENV_DATA_MISSING**: Page rendered cleanly but runs table shows empty state because no seed data — prefix reason with `ENV_DATA_MISSING:`.

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00074/reports/F-00074_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short specific reason>" \
  --report ai-dev/active/F-00074/reports/F-00074_S13_BrowserVerification_Report.md
```

## Report

Write `ai-dev/active/F-00074/reports/F-00074_S13_BrowserVerification_Report.md` with:
- Pass/fail table for V1–V6.
- Exact `$IW_BROWSER_BASE_URL` used.
- List of screenshots captured.
- No regressions subsection.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "F-00074",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "Page loads + nav entry", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Add slot + timeline update", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Toggle slot badge", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Runs table visible", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Config save", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
