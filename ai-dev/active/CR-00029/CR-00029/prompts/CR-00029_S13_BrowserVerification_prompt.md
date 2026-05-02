# Browser Verification Prompt: CR-00029-S13-BrowserVerification

**Work Item**: CR-00029 -- Add Restart button to the synthetic Worktree Setup (S00) row
**Step**: S13
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute Docker mutating commands. Allowed: testcontainers via pytest, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. Do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use the env var.

Do NOT run any of:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser` — use `playwright-cli` exclusively
- Any `chromium.launch()` Python/Node snippet

## Input Files

- `ai-dev/active/CR-00029/CR-00029_CR_Design.md` -- the design document
- `dashboard/routers/items.py` (modified by S01)
- `dashboard/routers/actions.py` (modified by S01)
- `dashboard/templates/components/action_button.html` (modified by S03)
- `dashboard/templates/fragments/item_overview.html` (modified by S03)

## Output Files

- `ai-dev/active/CR-00029/reports/CR-00029_S13_BrowserVerification_Report.md`
- `ai-dev/active/CR-00029/evidences/post/` -- screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the dashboard requires login (check via `playwright-cli snapshot`), log in:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:
1. Always `playwright-cli snapshot` before `fill` / `click`
2. Wait for transitions to settle before snapshotting again
3. Screenshots: `playwright-cli screenshot` (no path arg), then `cp .playwright-cli/page-*.png ai-dev/active/CR-00029/evidences/post/CR-00029_v{N}_<short_name>.png`

## E2E DB seed data (REQUIRED — do not depend on production seed state)

CR-00029 needs two seeded items: one in a setup-recoverable state (to verify the new button appears + works) and one that has progressed past setup (to verify the button is hidden). Both **MUST** be created by a self-contained e2e fixture. **Do not assume any item from the production seed is in a particular state — items can change state at any time.**

Create the fixture file:

```
ai-dev/active/CR-00029/e2e_fixtures/001_restart_setup_targets.py
```

The fixture exports `def seed(db: Session) -> None:` and is idempotent (check existence before insert). It must seed:

**Item A — `CR29-A` (button SHOULD appear):**
- Project: existing `iw-ai-core` (do not create a new project).
- Work item id `CR29-A`, status `failed`.
- Batch `BATCH-CR29` (status `completed_with_errors`).
- BatchItem (status `failed`, `work_item_id=CR29-A`, no `step_runs`).
- WorkflowSteps for `CR29-A`: at least 3 entries, all status `pending`, no `started_at`.

**Item B — `CR29-B` (button should NOT appear):**
- Same project + same `BATCH-CR29` batch.
- Work item id `CR29-B`, status `completed`.
- BatchItem (status `completed`, `work_item_id=CR29-B`).
- WorkflowSteps for `CR29-B`: at least 3 entries, at least one with status `completed` and `started_at` set (so `restartable=False`).

Both items are synthesized just for this test — they MUST NOT collide with any real `I-NNNNN`/`F-NNNNN`/`CR-NNNNN` id. Use the literal ids `CR29-A` and `CR29-B`.

Re-seed inside the `app` container after writing the fixture:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell.**

If the fixture cannot be loaded (e.g., schema drift), call `iw step-fail` with `ENV_DATA_MISSING:` prefix.

## Verification Steps

### V1: Restart Setup button visible on a setup-failed S00 row

1. Navigate to `${IW_BROWSER_BASE_URL}/project/iw-ai-core/item/CR29-A` (the fixture-seeded restartable item).
2. Locate the Step Pipeline → step table → the row labelled "Worktree Setup" (S00) with status `failed`.
3. **Verify:** The row's right-most action column contains a button with text containing "Restart Setup" (the `↻` glyph is decorative).
4. **Verify:** The button has a `title` attribute (hover tooltip).
5. **Screenshot:** `ai-dev/active/CR-00029/evidences/post/CR-00029_v1_button_visible.png`.

### V2: Confirm dialog wording

1. Click the "Restart Setup" button.
2. Wait for the htmx swap to render the confirm dialog (target `#confirm-dialog`).
3. **Verify:** The dialog title contains "Restart setup CR29-A?" and the body contains "This deletes the worktree and resets every step." (the dispatcher renders the title as `f"{title.rstrip('?')} {item_id}?"`).
4. **Verify:** The dialog has a confirm button (label "Restart Setup" or similar) and a cancel button.
5. **Screenshot:** `ai-dev/active/CR-00029/evidences/post/CR-00029_v2_confirm_dialog.png`.

### V3: Click Cancel — no state change

1. From V2, click the dialog's Cancel button.
2. **Verify:** The dialog closes and the item-overview page is unchanged. The S00 row is still `failed` with the Restart Setup button still present.
3. **Verify:** No console errors.
4. **Screenshot:** `ai-dev/active/CR-00029/evidences/post/CR-00029_v3_cancel_no_change.png`.

### V4: Click Confirm — state resets

1. Click the "Restart Setup" button again to reopen the dialog.
2. Click the confirm button in the dialog.
3. Wait for the htmx response and any page reload.
4. **Verify:** The item header / status badge transitions away from `failed` (likely `approved` immediately, or `setting_up` after one daemon poll).
5. **Verify:** The S00 row's status badge is no longer `failed` — it should be `pending` (waiting for daemon) or `setting_up` (daemon picked it up).
6. **Verify:** The Restart Setup button is no longer visible (because `restartable` is now False).
7. **Verify:** No console errors during the click + swap.
8. **Screenshot:** `ai-dev/active/CR-00029/evidences/post/CR-00029_v4_post_restart.png`.

If the daemon poll cadence makes the post-confirm state hard to observe in time, capture the immediate post-swap state and document the timing in the report. The unit/integration tests in S05 verify the state transition deterministically.

### V5: Button does NOT appear on items that have progressed past setup

1. Navigate to `${IW_BROWSER_BASE_URL}/project/iw-ai-core/item/CR29-B` (the fixture-seeded post-setup item with at least one completed WorkflowStep).
2. **Verify:** The S00 "Worktree Setup" row appears in the Step Pipeline.
3. **Verify:** No "Restart Setup" button is visible on that row (because a progressed step disqualifies `restartable`).
4. **Screenshot:** `ai-dev/active/CR-00029/evidences/post/CR-00029_v5_no_button_post_setup.png`.

### V6: No regressions

1. Revisit the batch detail page — existing action buttons (Restart step, Skip, Kill, Retry merge) still render where expected.
2. Verify no new console errors on any page visited during V1..V5.
3. The MERGE row's Retry merge button still renders for items in failed-merge state.
4. **Screenshot:** `ai-dev/active/CR-00029/evidences/post/CR-00029_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Any failure — including a partial result — requires `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — page returned an HTTP error, threw a console exception, rendered the wrong element. Use a normal `--reason`.
- **ENV_DATA_MISSING** — page rendered cleanly with HTTP 200 but showed an empty-state because the E2E DB lacks a setup-failed item. Prefix the reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 expects fixture-seeded CR29-A (BatchItem in failed status, all WorkflowSteps pending) — verify ai-dev/active/CR-00029/e2e_fixtures/001_restart_setup_targets.py loaded" \
    --report ai-dev/active/CR-00029/reports/CR-00029_S13_BrowserVerification_Report.md
  ```

## Report

Write `ai-dev/active/CR-00029/reports/CR-00029_S13_BrowserVerification_Report.md` containing:

- A pass/fail table per V1..V6
- The exact `$IW_BROWSER_BASE_URL` used
- Any issues found with `file:line` references
- A list of screenshots captured
- A **No regressions observed** subsection covering V6

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00029/reports/CR-00029_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00029/reports/CR-00029_S13_BrowserVerification_Report.md
```

Always include `--report`.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "CR-00029",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "button visible", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "confirm dialog", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "cancel no-op", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "confirm resets state", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "button hidden post-setup", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "no regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
