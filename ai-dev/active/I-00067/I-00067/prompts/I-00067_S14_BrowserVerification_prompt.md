# Browser Verification Prompt: I-00067-S14-BrowserVerification

**Work Item**: I-00067 -- Recent Activity messages need truncation + click-to-expand popup
**Step**: S14
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. Do not run `docker compose up/down/restart/build` or any equivalent — the orchestrator has already provisioned the isolated worktree stack. `docker compose exec app` is allowed (and required) when re-running the seed after writing a fixture file.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Environment

The IW orchestrator has already started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var. Do NOT run `make dev`, `make test-e2e`, `make e2e-up`, `playwright install`, `npx playwright install`, `agent-browser`, or any direct `chromium.launch()` snippet. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00067/I-00067_Issue_Design.md`
- `dashboard/templates/pages/project/dashboard.html`
- `dashboard/templates/fragments/activity_text_modal.html`
- `dashboard/static/styles.css`
- `tests/integration/test_i00067_recent_activity_truncation.py`

## Output Files

- `ai-dev/active/I-00067/reports/I-00067_S14_BrowserVerification_Report.md`
- `ai-dev/active/I-00067/evidences/post/` — screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If login is required for the dashboard, log in with `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD` using the snapshot-then-fill-then-click pattern.

## E2E DB seed data

The worktree stack's PostgreSQL is seeded from production via `pg_dump`. To force-create a long activity message for a clean reproduction, add a fixture under `ai-dev/active/I-00067/e2e_fixtures/001_long_activity_message.py` that exports `def seed(db: Session) -> None` and inserts a `DaemonEvent` row with a >100-char message into the iw-ai-core project. After writing the fixture, re-run the seed inside the `app` container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ NEVER run the seed from your host shell. Only run it via `docker compose exec app`.

If the seed already contains long messages organically, you may skip the fixture.

## Verification Steps

### V1: Long messages truncate to 100 chars + "..."

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/`.
2. `playwright-cli snapshot` — locate the "Recent Activity" card.
3. **Verify**: at least one row in the card has its visible message text ending with the literal three ASCII characters `...`. The visible portion before `...` is exactly 100 characters of the original message.
4. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00067/evidences/post/I-00067_v1_truncated_row.png` (after running `playwright-cli screenshot` first).

### V2: Clicking a truncated row opens the popup with full text

1. Still on `$IW_BROWSER_BASE_URL/project/iw-ai-core/`.
2. `playwright-cli snapshot` — find the truncated row's clickable element (the one with the `activity-message-truncated` class or whichever trigger the implementation chose).
3. `playwright-cli click <truncated-row-ref>` — this opens the activity-text modal.
4. `playwright-cli snapshot` — confirm a modal/dialog is now visible.
5. **Verify**: the modal body contains the FULL untruncated message text (longer than 100 chars, no `...`, includes characters after the 100th codepoint).
6. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00067/evidences/post/I-00067_v2_popup_open.png`.

### V3: Modal dismissal — close button, ESC, click-outside

1. With the modal open from V2, click the modal's close button (`×` or labelled close).
2. `playwright-cli snapshot` — confirm the modal is hidden (`aria-hidden="true"` or removed from accessibility tree).
3. Re-open the modal (repeat V2 click).
4. Press ESC: `playwright-cli press Escape` (or whichever playwright-cli verb is correct in this environment — fall back to clicking outside the modal if `press` is unavailable).
5. Confirm the modal is hidden.
6. Re-open the modal a third time and click on the overlay/backdrop (outside the inner card).
7. Confirm the modal is hidden.
8. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00067/evidences/post/I-00067_v3_modal_dismissed.png`.

### V4: Short messages render verbatim with NO "..." and NO click affordance

1. `playwright-cli snapshot` of the Recent Activity card.
2. Find a row whose original message is ≤100 chars (e.g., a short merge or step-launched event).
3. **Verify**: the visible text does NOT end with `...`. The row does NOT have the `activity-message-truncated` class. Clicking it does NOT open the modal (perform the click and then snapshot to confirm the modal is still hidden).
4. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00067/evidences/post/I-00067_v4_short_no_affordance.png`.

### V5: No Regressions

1. Visit `$IW_BROWSER_BASE_URL/project/iw-ai-core/` and confirm batch / doc_job / work_item entity-link badges in the Recent Activity card still navigate correctly. Click a `BATCH-...` link from a row whose `entity_type` was already correctly set; confirm the URL is `/project/iw-ai-core/batch/BATCH-...` and the page loads (200, not the I-00068 bug — that is verified separately in I-00068's browser step).
2. Confirm no new console errors appeared on any page visited during V1..V4.
3. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00067/evidences/post/I-00067_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure requires `iw step-fail`. If the dashboard renders cleanly but no organic event is long enough to trigger truncation, classify the failure as `ENV_DATA_MISSING:` and reference adding `ai-dev/active/I-00067/e2e_fixtures/001_long_activity_message.py`.

## Report

Write `ai-dev/active/I-00067/reports/I-00067_S14_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- A list of the screenshots captured.
- A "No regressions observed" subsection.

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00067/reports/I-00067_S14_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00067/reports/I-00067_S14_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "I-00067",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "long messages truncate to 100 + '...'", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "click truncated row opens popup with full text", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "modal dismissal (close / ESC / outside)", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "short messages render verbatim, no affordance", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "no regressions on entity links and console", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
