# Browser Verification Prompt: CR-00078-S19-BrowserVerification

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S19
**Agent**: qv-browser

---

## ⛔ Docker is off-limits
(The orchestrator's E2E stack is already running.)

## ⛔ Migrations: agents generate, daemon applies
The migration is already applied in the e2e stack by the worktree-bootstrap path.

## Environment

- `$IW_BROWSER_BASE_URL` — base URL of the worktree's e2e dashboard.
- `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD` — credentials.
- `$IW_ITEM_ID` / `$IW_STEP_ID` — set by the harness.

Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/CR-00078/CR-00078_CR_Design.md`
- `dashboard/templates/fragments/batch_overlap_modal.html`
- `dashboard/static/styles.css`
- `dashboard/routers/actions.py`

## Output Files

- `ai-dev/active/CR-00078/reports/CR-00078_S19_BrowserVerification_Report.md`
- `ai-dev/active/CR-00078/evidences/post/` — screenshots.

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

The seed DB is `pg_dump`-restored from production; BATCH-00127 with its 5 Held items should be present. If not, find any held item in the e2e dashboard.

### Seed gap fallback

If the e2e stack has zero held items (because production cleared the conflict before the worktree was provisioned), add an `ai-dev/active/CR-00078/e2e_fixtures/001_held_item.py` per the QvBrowser template's seed-on-demand pattern: insert a `Project`, a `Batch` with `status='executing'`, two `WorkItem` rows, a `BatchItem` for the held item, and two `DaemonEvent` rows of type `item_held_for_scope` with realistic `event_metadata` containing 4-5 distinct `conflicting_globs`. Re-run the seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

## Verification Steps

### V1: Open modal — confirms CR-00077 trigger still works after this CR's changes

1. Navigate to the batch detail Items tab via UI.
2. Click the `Held: …` pill.
3. **Verify:** Modal opens with at least one section + file list + a master "Ignore all & start" button at the bottom + per-file "Ignore" buttons.
4. **Screenshot:** `CR-00078_v1_modal_with_buttons.png`.

### V2: Per-file Ignore — row disappears (AC1)

1. With the modal open, identify a file row and note its glob text.
2. Click that row's "Ignore" button.
3. Snapshot.
4. **Verify:** That specific `<li>` is gone from the modal. Other file rows in the same section remain. The master "Ignore all & start" button is still present.
5. **Screenshot:** `CR-00078_v2_per_file_ignore.png`.

### V3: Reopen modal — ignored file does not return (AC1, server-side filter)

1. Close the modal (Esc, ×, or backdrop).
2. Click the `Held: …` pill again.
3. Snapshot.
4. **Verify:** The file ignored in V2 is NOT in the reopened modal. The remaining files are still visible.
5. **Screenshot:** `CR-00078_v3_reopen_filtered.png`.

### V4: Master "Ignore all & start" — modal closes, item transitions (AC3)

1. With the modal open, click "Ignore all & start".
2. Confirm the htmx-native `confirm()` dialog.
3. Snapshot — modal should be gone.
4. **Wait** up to 75 seconds (one daemon poll cycle ~60s + buffer) and refresh the Items tab page periodically.
5. Snapshot the row for the previously-held item.
6. **Verify:** The held item is no longer shown as `Held: overlaps with …`. Its status is `pending → setting_up → executing` (one of these is acceptable depending on the poll moment).
7. **Screenshot:** `CR-00078_v4_master_button_release.png`.

If the daemon poll interval in the e2e stack differs from production, allow more time or read `IW_CORE_POLL_INTERVAL` from the env if available.

### V5: Timeline shows ignore events (AC6)

1. Navigate to the batch detail Timeline tab (`?tab=timeline`).
2. Snapshot.
3. **Verify:** The timeline shows the lines from CR-00078 §5 for each ignore action taken during V2 and V4 — at minimum one `Operator ignored overlap on <file> with <blocking_item>` row from V2 and one `Operator ignored all <N> remaining overlaps for <held_item>` from V4.
4. **Screenshot:** `CR-00078_v5_timeline_audit.png`.

### V6: No regressions on a clean batch

1. Navigate to a batch that has no held items.
2. Click into any pending or running item's pill area (where the Held pill would have been).
3. **Verify:** Nothing breaks. No modal opens unexpectedly. No console errors on the page (read `.playwright-cli/console-*.log`).
4. **Screenshot:** `CR-00078_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. V4 may legitimately fall back to `ENV_DATA_MISSING:` if the daemon is not running in the e2e stack (rare).

## Report

Standard `iw step-done` / `iw step-fail` per the template.

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "qv-browser",
  "work_item": "CR-00078",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<concrete URL>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Modal opens with buttons", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Per-file Ignore removes row", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Reopen modal filters ignored", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Master button releases item", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Timeline shows audit lines", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions on clean batch", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
