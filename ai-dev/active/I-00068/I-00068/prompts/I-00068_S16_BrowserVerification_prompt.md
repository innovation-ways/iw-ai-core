# Browser Verification Prompt: I-00068-S16-BrowserVerification

**Work Item**: I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/
**Step**: S16
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. Do not run `docker compose up/down/restart/build` or any equivalent. `docker compose exec app` is allowed (and required) when re-running the seed after writing a fixture file.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Environment

The IW orchestrator has already started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var. Do NOT run `make dev`, `make test-e2e`, `make e2e-up`, `playwright install`, `npx playwright install`, `agent-browser`, or any direct `chromium.launch()` snippet. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00068/I-00068_Issue_Design.md`
- `orch/archive/batch_archiver.py`
- `dashboard/templates/pages/project/dashboard.html`
- `tests/integration/test_i00068_batch_link_routing.py`

## Output Files

- `ai-dev/active/I-00068/reports/I-00068_S16_BrowserVerification_Report.md`
- `ai-dev/active/I-00068/evidences/post/` — screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If login is required, log in with `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD` using the snapshot-then-fill-then-click pattern.

## E2E DB seed data

The worktree stack's PostgreSQL is seeded from production. The verification needs at least one Recent Activity event whose `entity_id` starts with `BATCH-`. Both of these are sufficient:

- A `DaemonEvent` with `entity_type="batch"` and `entity_id="BATCH-XXXXX"` (from the `batch_executing` / `batch_completed` flow).
- A `DaemonEvent` with `entity_type=None` and `entity_id="BATCH-XXXXX"` (the legacy/buggy emission this fix targets).

If neither is present in the seeded DB, add a fixture under `ai-dev/active/I-00068/e2e_fixtures/001_batch_archive_events.py` that exports `def seed(db: Session) -> None` and inserts one `DaemonEvent` with `entity_id="BATCH-99999"` and `entity_type=None`, plus another with `entity_type="batch"`. Then re-run the seed:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ NEVER run the seed from your host shell.

## Verification Steps

### V1: Recent Activity row with entity_type=None and BATCH- ID renders /batch/ link

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/`.
2. `playwright-cli snapshot` — locate the Recent Activity card.
3. Find a row whose visible text mentions a batch ID (e.g., `Batch BATCH-99999 archived successfully` or any other event referring to a `BATCH-` ID). If only the seeded fixture row is available, that's fine.
4. **Verify**: the snapshot shows the link href ending in `/batch/BATCH-99999` (or whichever batch ID), NOT `/item/BATCH-99999`.
5. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00068/evidences/post/I-00068_v1_dashboard_links.png`.

### V2: Click navigates to batch detail page (no 404)

1. Click the batch link from V1: `playwright-cli click <batch-link-ref>`.
2. `playwright-cli snapshot` — confirm the new page is the batch detail page.
3. **Verify**:
   - Current URL is `$IW_BROWSER_BASE_URL/project/iw-ai-core/batch/BATCH-99999` (or whichever batch).
   - HTTP status was 200 (no 404 JSON error like `{"detail":"Work item ... not found"}`).
   - The page renders batch detail content (e.g., a heading containing the batch ID, a list of items in the batch, etc.).
4. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00068/evidences/post/I-00068_v2_batch_detail.png`.

### V3: New archive events carry entity_type="batch" (verified via dashboard rendering)

1. Navigate back to `$IW_BROWSER_BASE_URL/project/iw-ai-core/`.
2. If a recent `Batch ... archived successfully` row appears (from a real archive operation OR from seed data with `entity_type="batch"`), confirm its href is `/batch/...` (not `/item/...`).
3. If no such row exists in the seed, this verification is satisfied by V1 (the more robust prefix-check rule). Document this in the report.
4. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00068/evidences/post/I-00068_v3_archive_event.png`.

### V4: Non-batch IDs still route to /item/

1. From the same Recent Activity card, find a row with a work-item ID (e.g., `I-00063`, `CR-00030`).
2. **Verify**: that row's link href is `/item/I-00063` or `/item/CR-00030` (the existing fallback continues to work).
3. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00068/evidences/post/I-00068_v4_work_item_unchanged.png`.

### V5: No Regressions

1. Confirm the doc-job link routing still works: find a doc-job row, click it, confirm it lands on `/jobs/doc/...`.
2. Confirm no new console errors appeared on any page visited during V1..V4.
3. **Screenshot**: `cp .playwright-cli/page-*.png ai-dev/active/I-00068/evidences/post/I-00068_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure requires `iw step-fail`. If no `BATCH-` row exists in the seed, classify as `ENV_DATA_MISSING:` and add the fixture.

## Report

Write `ai-dev/active/I-00068/reports/I-00068_S16_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- A list of the screenshots captured.
- A "No regressions observed" subsection.

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00068/reports/I-00068_S16_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00068/reports/I-00068_S16_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "I-00068",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "BATCH- ID with entity_type=None renders /batch/ link", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "click navigates to batch detail page (no 404)", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "archive event renders /batch/ link", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "non-batch IDs still route to /item/", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "no regressions on doc-job links and console", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
