# Browser Verification Prompt: F-00082-S15-BrowserVerification

**Work Item**: F-00082 -- Dashboard Cancel Buttons (Batch + Work Item)
**Step**: S15
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Read-only `docker ps` / `docker inspect` / `docker logs` are allowed. The E2E stack was started by the orchestrator before this prompt ran. `docker compose exec app` is allowed when re-running the seed after writing a fixture file.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are not generating migrations in this step. If the verification stack reports an alembic mismatch, that is a daemon-side issue — flag and fail with a clear reason.

## Environment

The IW orchestrator has already started an isolated E2E stack built from THIS worktree's source code. Do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or application route paths. Navigate via the UI: open the project dashboard (`$IW_BROWSER_BASE_URL/project/iw-ai-core/`) and click into the lists rather than typing detail URLs. Treat any 404 as a `SPEC_MISMATCH`.

Before asserting on the content of any page, confirm the page itself loaded (HTTP 200, no unhandled exception, no load-time JS/HTMX console errors).

## Input Files

- `ai-dev/active/F-00082/F-00082_Feature_Design.md` (read §Acceptance Criteria; each AC maps to a V step below).
- Files modified by S01 / S03 / S05 (per their reports).

## Output Files

- `ai-dev/active/F-00082/reports/F-00082_S15_BrowserVerification_Report.md`.
- Screenshots under `ai-dev/active/F-00082/evidences/post/`.

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in if the test stack has auth (this project runs without auth in dev, so likely no login screen — confirm by snapshotting the root page).

## E2E DB seed data

The E2E DB is seeded from production. F-00082's verifications need:
- A batch in `paused` or `executing` status with at least one BatchItem in `executing` or `pending` (so AC1 / AC4 / AC5 have a real target).
- A work item in `in_progress` status not in any active batch (so AC2 has a target).
- A work item in `in_progress` status that IS in an active batch (so AC3 has a target).

If the seed lacks these, add a fixture under `ai-dev/active/F-00082/e2e_fixtures/001_cancel_targets.py` that idempotently creates them, then re-run the seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

NEVER run the seed from the host shell — `.env` resolves to the production DB on port 5433.

## Verification Steps

### V1: Cancel an executing batch with `--reset-items` (AC1)

1. Navigate to the project's `/batches` list and click into a batch with status `executing` or `paused`. (If none exists, add it via the fixture file described above.)
2. On the batch detail page, click the **Cancel Batch** button next to Pause/Resume — this triggers the GET that fetches the form-bearing confirm modal.
3. In the modal: type "browser verification" into the reason textarea; tick "Also reset member items to draft"; click **Cancel Batch**.
4. **Verify:**
   - The modal closes.
   - A toast appears containing the text `Cancelled BATCH-` and the reason "browser verification".
   - The page header now shows status `cancelled` (refresh the page if htmx swap depended on `reload=True`).
   - The Cancel button is no longer visible.
   - The batch's items section shows each member with status `skipped`.
5. **Screenshot:** `playwright-cli screenshot && cp .playwright-cli/page-*.png ai-dev/active/F-00082/evidences/post/F-00082_v1_batch_cancelled_reset.png`.

### V2: Cancel a standalone work item (AC2)

1. Navigate to the project's queue or history list and click into a work item with status `in_progress` that is NOT in an active batch. (If none exists, add via fixture.)
2. On the item detail page, click the **Cancel Item** button (enabled, not the disabled hint variant).
3. In the modal: leave reason as default; do NOT tick "Reset to draft"; click **Cancel Item**.
4. **Verify:**
   - Toast contains `Cancelled CR-` (or `I-` / `F-` depending on type) with the default reason.
   - Page header shows status `cancelled`.
5. **Screenshot:** `…/F-00082_v2_item_cancelled.png`.

### V3: In-active-batch item shows disabled hint (AC3)

1. Navigate to the detail page of a work item that IS in an active batch.
2. **Verify:**
   - The Cancel button is rendered but DISABLED (visually de-emphasised, not clickable).
   - A hint paragraph below reads "Belongs to active batch BATCH-XXXXX — cancel the batch instead." with a hyperlink on the batch ID.
   - Click the batch link.
   - The browser navigates to the batch detail page.
3. **Screenshot:** `…/F-00082_v3_item_disabled_hint.png`.

### V4: Quick-cancel from the batches list (AC4)

1. Navigate to the project's `/batches` list.
2. Locate a row for a batch in a cancellable status. Click the per-row "✕" / "Cancel" icon-button.
3. **Verify:** the browser's `confirm()` dialog appears with text containing `Cancel BATCH-`. Accept it.
4. **Verify after htmx swap:**
   - The row updates in place: status column shows `cancelled`.
   - No full page reload occurred (the URL did not change; the page header did not flash).
5. **Screenshot:** `…/F-00082_v4_quick_cancel_row.png`.

### V5: Terminal batch — no Cancel button (AC5)

1. Navigate to a batch in `completed` or `archived` status.
2. **Verify:** no Cancel button is rendered anywhere on the detail page header.
3. **Snapshot the DOM** and `grep` for "Cancel Batch" in the saved snapshot — must be absent.
4. **Screenshot:** `…/F-00082_v5_terminal_no_button.png`.

### V6: Audit event surfacing

1. After V1 (cancelling a batch), navigate to the project's jobs / events page.
2. **Verify:** a recent row shows event_type `batch_cancelled` with the batch ID and the reason "browser verification" in the message column.
3. **Screenshot:** `…/F-00082_v6_audit_event.png`.

### V7: No Regressions

1. Revisit the existing Approve / Pause / Resume flows on a planning / executing batch — open each confirm modal, confirm the rendered HTML still matches pre-F-00082 (no stray form fields, button text unchanged). Cancel the modal without submitting.
2. Revisit the project's queue page — the existing per-row cancel button on a `draft` item still works (queue.html path).
3. Check `.playwright-cli/console-*.log` for any new errors from V1..V6.
4. **Screenshot:** `…/F-00082_v7_no_regressions.png`.

## Pass Criteria

All V1..V7 must pass. Failure handling:

- 5xx page / unhandled console exception → `CODE_DEFECT` (normal `--reason`).
- Page rendered cleanly but expected fixture row missing → `ENV_DATA_MISSING` (add fixture, re-seed, retry).
- Page rendered cleanly, element correctly absent per design, V asks for it anyway → `SPEC_MISMATCH` (cite the design line).

## Report

Write `ai-dev/active/F-00082/reports/F-00082_S15_BrowserVerification_Report.md` with:

- Per-V pass/fail table.
- The exact `$IW_BROWSER_BASE_URL` used.
- List of screenshots captured.
- A "No regressions observed" subsection.

Then call:

```bash
# pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00082/reports/F-00082_S15_BrowserVerification_Report.md

# fail
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00082/reports/F-00082_S15_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "F-00082",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<concrete URL>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Cancel executing batch with reset_items", "status": "pass|fail", "failure_class": "null", "screenshot": "evidences/post/F-00082_v1_batch_cancelled_reset.png", "notes": ""},
    {"id": "V2", "name": "Cancel standalone work item", "status": "pass|fail", "failure_class": "null", "screenshot": "evidences/post/F-00082_v2_item_cancelled.png", "notes": ""},
    {"id": "V3", "name": "Disabled hint when in active batch", "status": "pass|fail", "failure_class": "null", "screenshot": "evidences/post/F-00082_v3_item_disabled_hint.png", "notes": ""},
    {"id": "V4", "name": "Quick-cancel from list", "status": "pass|fail", "failure_class": "null", "screenshot": "evidences/post/F-00082_v4_quick_cancel_row.png", "notes": ""},
    {"id": "V5", "name": "No button on terminal batch", "status": "pass|fail", "failure_class": "null", "screenshot": "evidences/post/F-00082_v5_terminal_no_button.png", "notes": ""},
    {"id": "V6", "name": "Audit event surfaced", "status": "pass|fail", "failure_class": "null", "screenshot": "evidences/post/F-00082_v6_audit_event.png", "notes": ""},
    {"id": "V7", "name": "No regressions", "status": "pass|fail", "failure_class": "null", "screenshot": "evidences/post/F-00082_v7_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
