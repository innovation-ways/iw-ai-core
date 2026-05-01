# Browser Verification Prompt: I-00059-S11-BrowserVerification

**Work Item**: I-00059 -- Doc Generation Job Detail Page Shows No Error Info or Parameters
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. Do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use `$IW_BROWSER_BASE_URL`.

Do NOT run `make dev`, `make e2e-up`, `docker compose`, `playwright install`, or `agent-browser`.
Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00059/I-00059_Issue_Design.md` — design document
- `orch/jobs/aggregator.py` — fixed file (S01)

## Output Files

- `ai-dev/active/I-00059/reports/I-00059_S11_BrowserVerification_Report.md`
- `ai-dev/active/I-00059/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
playwright-cli snapshot   # find login field refs
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

## E2E DB seed data

The E2E stack is seeded from the production orchestration DB via `pg_dump`. Job `2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435` (status=failed, error="generation timeout after 15 minutes", skill_used="iw-doc-generator", duration_seconds=600, doc_id="iw-ai-core:code-index") exists in production and will be available in the E2E DB.

If the job is not present (ENV_DATA_MISSING), add a fixture at `ai-dev/active/I-00059/e2e_fixtures/001_i00059_doc_job.py` that seeds a failed `DocGenerationJob` row.

## Verification Steps

### V1: Error block visible for failed job

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/jobs/doc_generation/2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435`.
2. Scroll to the bottom of the page — this triggers rendering of the Error block if the `raw.error` field is populated.
3. **Verify:** A red/destructive-styled "Error" section is visible and contains the text `generation timeout after` (partial match is fine).
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00059/evidences/post/I-00059_v1_error_block.png`.

### V2: Parameters card shows skill_used and duration_seconds

1. On the same page (no navigation needed).
2. Observe the "Parameters" card near the top of the page.
3. **Verify:** The Parameters card contains `skill_used` with value `iw-doc-generator` AND `duration_seconds` with a numeric value (600 or 900 — either is acceptable).
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00059/evidences/post/I-00059_v2_parameters.png`.

### V3: View document link present

1. On the same page.
2. Observe the Parameters card footer.
3. **Verify:** A "→ View document" link is visible (doc_id is `iw-ai-core:code-index` — the link should point to that doc).
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00059/evidences/post/I-00059_v3_doc_link.png`.

### V4: No regressions — jobs list still renders

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/jobs`.
2. Verify the jobs list renders without errors and `doc_generation` rows appear.
3. Click into any other job detail page to verify the detail route still works for non-failed jobs.
4. **Verify:** No console errors. Jobs list renders normally.
5. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00059/evidences/post/I-00059_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure requires calling `iw step-fail`. Classify as CODE DEFECT or ENV_DATA_MISSING before failing.

## Report

Write `ai-dev/active/I-00059/reports/I-00059_S11_BrowserVerification_Report.md` with:
- Pass/fail table for V1..V4
- The exact `$IW_BROWSER_BASE_URL` used
- Screenshots list
- No regressions subsection

Then call:
```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00059/reports/I-00059_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short reason>" \
  --report ai-dev/active/I-00059/reports/I-00059_S11_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00059",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "Error block visible", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Parameters card shows skill_used/duration", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "View document link present", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "No regressions — jobs list", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
