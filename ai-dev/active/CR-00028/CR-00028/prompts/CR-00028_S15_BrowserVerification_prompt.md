# Browser Verification Prompt: CR-00028-S15-BrowserVerification

**Work Item**: CR-00028 -- Don't cascade merge-time failures to dependent items
**Step**: S15
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

Do NOT run any of the following:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser` — use `playwright-cli` exclusively
- Any `chromium.launch()` Python/Node snippet

## Input Files

- `ai-dev/active/CR-00028/CR-00028_CR_Design.md` -- the design document
- `orch/db/models.py` (modified by S01)
- `orch/db/migrations/versions/<rev>_cr00028_*.py` (created by S01)
- `orch/daemon/merge_queue.py` (modified by S03)
- `orch/daemon/batch_manager.py` (modified by S03)
- `dashboard/routers/actions.py` (modified by S03)
- `dashboard/templates/components/**.html` and/or `dashboard/templates/fragments/**.html` (modified by S05)

## Output Files

- `ai-dev/active/CR-00028/reports/CR-00028_S15_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00028/evidences/post/` -- screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

(If the dashboard does not require login in this E2E stack — see existing patterns — skip the login flow.)

Rules:
1. Always `playwright-cli snapshot` before `fill` / `click`
2. Wait for navigation/transitions to settle before snapshotting again
3. Screenshots go to `ai-dev/active/CR-00028/evidences/post/` with descriptive filenames

## E2E DB seed data

The E2E PostgreSQL is seeded from the production orchestration DB via `pg_dump`. CR-00028 introduces the `merge_failed` enum value and changes cascade behavior — this requires synthetic test data because production won't have a `merge_failed` row at fresh seed time.

**Add a fixture** at `ai-dev/active/CR-00028/e2e_fixtures/001_merge_failed_batch.py` that seeds:

- One Project (or use existing)
- One Batch in `executing` status
- Two BatchItems:
  - I1 in `merge_failed` (group=1)
  - I2 in `pending` (group=2)
- One Batch in `completed_with_errors` (legacy state) for the regression check

Make the fixture idempotent (`db.get(...)` before insert) and follow the pattern from existing fixtures under other items' `e2e_fixtures/` dirs.

After writing the fixture, re-run the seed inside the `app` container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell.**

If the fixture requires data that isn't yet expressible (e.g., the migration hasn't applied), call `iw step-fail` with `ENV_DATA_MISSING:` prefix.

## Verification Steps

### V1: `merge_failed` badge renders distinctly from `failed`

1. Navigate to `${IW_BROWSER_BASE_URL}/project/iw-ai-core/batches`.
2. Locate the batch containing the seeded I1 (status `merge_failed`). The batches table renders BatchItem statuses via the `status_badge` macro.
3. **Verify:**
   - The I1 row's status cell shows the `merge_failed` badge in a color **distinct from red** (the design uses the existing `bg-warning` token).
   - For comparison, if a legacy `failed` item is visible elsewhere (e.g. BATCH-00070's I-00056 in production seed, if present), its badge is red — confirming the two are visually distinguishable.
4. **Screenshot:** `ai-dev/active/CR-00028/evidences/post/CR-00028_v1_merge_failed_badge.png`.

### V2: Retry-merge button on the item-overview page (synthetic MERGE step row)

The action buttons live on the item-overview page (under the synthetic MERGE step), NOT inline in the batch-detail rows.

1. Navigate to `${IW_BROWSER_BASE_URL}/project/iw-ai-core/item/<I1_id>`.
2. Locate the synthetic MERGE step row in the step pipeline / step detail table.
3. **Verify:** A "Retry Merge" button is visible in the action column for the MERGE row.
4. Snapshot the page. **Verify:** the button's `hx-get` attribute equals `/project/<project_id>/api/confirm-item/restart-merge/<item_id>` (the confirm-modal pattern — NOT a direct `hx-post` and NOT an `hx-confirm` attribute).
5. **Screenshot:** `ai-dev/active/CR-00028/evidences/post/CR-00028_v2_retry_merge_button.png`.

### V3: Abandon button uses confirm-modal pattern

1. On the same item-overview page, locate the "Abandon" button on the synthetic MERGE row.
2. **Verify:** Its `hx-get` equals `/project/<project_id>/api/confirm-item/abandon-merge/<item_id>`. There is NO `hx-confirm` attribute (the dashboard does not use the browser-native dialog).
3. Click the button to load the confirm modal. **Verify:** the modal renders with a danger-styled "Abandon Merge" confirm button and an explanatory description (registered in `_ITEM_ACTION_LABELS["abandon-merge"]`).
4. **Screenshot:** `ai-dev/active/CR-00028/evidences/post/CR-00028_v3_abandon_modal.png`.

### V4: Confirm Retry-merge — item transitions out of merge_failed

1. From the item-overview page, click "Retry Merge". The confirm modal opens.
2. Click the modal's confirm button (which POSTs to `/api/item/<item_id>/restart-merge`).
3. Wait for the htmx fragment swap to complete.
4. **Verify:** The synthetic MERGE step's display status changes (away from `merge_failed`; likely `completed` or `in_progress` depending on daemon poll cadence).
5. **Verify:** No console errors appear during the click + swap.
6. **Screenshot:** `ai-dev/active/CR-00028/evidences/post/CR-00028_v4_retry_merge_clicked.png`.

(If the daemon's poll cadence makes the post-click state hard to observe, capture the immediate post-swap state and document the timing in the report. The unit/integration tests in S07 verify the state transition deterministically; this V4 is for the UI signal only.)

### V5: Confirm Abandon — observe status flip and cascade

1. Re-run the fixture seed (the previous test consumed the seeded `merge_failed` state).
2. Reload the item-overview page for I1.
3. Click "Abandon" on the synthetic MERGE row. Modal opens.
4. Click the modal's danger confirm button (POSTs to `/api/item/<item_id>/abandon-merge`).
5. **Verify:** I1's synthetic MERGE step status changes to `failed` (red badge).
6. Wait one daemon poll cycle (60s — or trigger a poll via `iw daemon ...` if available) and reload the batch-detail page.
7. **Verify:** I2 (group=2, was pending) now shows status `failed` with the cascade note.
8. **Screenshot:** `ai-dev/active/CR-00028/evidences/post/CR-00028_v5_abandon_cascade.png`.

(If the poll cadence makes V5.7 hard to observe within the step's timeout, capture the post-abandon state of I1 and note the cascade verification as deferred-to-integration-tests in your report. The integration test `test_abandon_merge_triggers_cascade.py` covers this deterministically.)

### V6: No Regressions

1. Revisit `${IW_BROWSER_BASE_URL}/project/iw-ai-core/batches` — the batches list still renders correctly.
2. Verify legacy `failed` / `completed_with_errors` items still render with their original red badge and existing action buttons (no regression on the cascade UI).
3. Verify no new console errors on any page visited during V1..V5.
4. **Screenshot:** `ai-dev/active/CR-00028/evidences/post/CR-00028_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — page returned an HTTP error, threw a console exception, rendered the wrong element. Use a normal `--reason`.
- **ENV_DATA_MISSING** — page rendered cleanly with HTTP 200 but showed an empty-state because the E2E DB lacks the seeded `merge_failed` row. Prefix the reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 expects a BatchItem in merge_failed status — re-seed via ai-dev/active/CR-00028/e2e_fixtures/001_merge_failed_batch.py" \
    --report ai-dev/active/CR-00028/reports/CR-00028_S15_BrowserVerification_Report.md
  ```

## Report

Write `ai-dev/active/CR-00028/reports/CR-00028_S15_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V6
- The exact `$IW_BROWSER_BASE_URL` used
- Any issues found with `file:line` references
- A list of the screenshots captured (relative paths under `evidences/post/`)
- A **No regressions observed** subsection covering V6

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00028/reports/CR-00028_S15_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00028/reports/CR-00028_S15_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "CR-00028",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "merge_failed badge", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "retry-merge button", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "abandon button + hx-confirm", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "retry-merge transitions item", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "abandon triggers cascade", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "no regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
