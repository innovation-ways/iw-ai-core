# Browser Verification Prompt: I-00045-S11-BrowserVerification

**Work Item**: I-00045 — OSS Status Widget and Page: Ugly Layout and Raw JSON Rendering
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits / Migrations policy

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var.

Use `playwright-cli` exclusively. Do NOT use `agent-browser`, `chromium.launch()`, or any install commands.

---

## Input Files

- `ai-dev/active/I-00045/I-00045_Issue_Design.md`
- `dashboard/templates/fragments/oss_status_frame.html`
- `dashboard/templates/pages/project/oss.html`

## Output Files

- `ai-dev/active/I-00045/reports/I-00045_S11_BrowserVerification_Report.md`
- `ai-dev/active/I-00045/evidences/post/` — screenshots taken during verification

---

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If login is required, take a snapshot first to read element refs, then fill credentials and submit.

---

## E2E DB Seed Data

The E2E stack starts with a fresh PostgreSQL with the schema and seed from `scripts/e2e_seed.py`. The seed includes a project row (slug `iw-ai-core` or as configured). To trigger the OSS widget, the seed must include an `OssScan` with a known `summary_json`. If such a scan is not present in the base seed:

Add an E2E fixture file:
```
ai-dev/active/I-00045/e2e_fixtures/001_oss_scan_seed.py
```

The file must export `def seed(db: Session) -> None` and insert a completed `OssScan` with:
```python
summary_json = {
    "must_fail": 4, "must_pass": 15, "should_fail": 9,
    "should_pass": 31, "may_pass": 4, "skip": 4, "total": 73,
}
```

Make the seed idempotent (check for existing row before inserting).

---

## Verification Steps

### V1: Dashboard widget — no raw JSON in pill

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/` (substitute `iw-ai-core` with the project slug from the E2E seed).
2. Locate the OSS Status widget (inside the "Git Status" panel).
3. **Verify**: The pill label shows a human-readable string (e.g., "50 passed · 4 critical · 9 warnings") — NOT a raw Python dict string like `{'skip':` or `'must_fail':`.
4. **Verify**: The page source (use `playwright-cli snapshot` or inspect element text) does NOT contain the strings `must_fail`, `{'skip'`, or `'total'`.
5. **Screenshot**: `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00045/evidences/post/I-00045_v1_no_raw_json.png`

### V2: Dashboard widget — "OSS STATUS" heading is a link

1. Remain on the same project dashboard page from V1.
2. Take a snapshot: `playwright-cli snapshot`
3. Find the "OSS Status" heading element in the snapshot.
4. **Verify**: The heading is rendered as an `<a>` element (the snapshot will show it as a `link` rather than `heading` or `generic`), with href pointing to `/project/iw-ai-core/oss`.
5. Click the "OSS Status" link.
6. **Verify**: Browser navigates to the OSS compliance page (`/project/iw-ai-core/oss`).
7. **Screenshot**: `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00045/evidences/post/I-00045_v2_heading_link.png`

### V3: Dashboard widget — stale banner has no white border box

1. Navigate back to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/`.
2. If the OSS scan is stale (HEAD has advanced since last scan), the stale warning banner should be visible.
3. **Verify**: The stale warning shows amber/yellow text and background tint — but no visible rectangular white border box around it.
4. If no stale banner is visible (scan is fresh), note this as "not applicable — scan is not stale" and skip to V4.
5. **Screenshot**: `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00045/evidences/post/I-00045_v3_stale_no_border.png`

### V4: OSS page — CSS dots, no emoji circles

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/oss`.
2. Locate the "Last scan:" status indicator at the top of the page.
3. **Verify**: The status indicator uses a small colored circle (CSS-styled dot) — NOT a Unicode emoji character (🔴, 🟡, 🟢).
4. Inspect the element text via snapshot — a CSS dot will appear as `●` or as an empty/SVG element, not as `🔴`.
5. **Screenshot**: `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00045/evidences/post/I-00045_v4_no_emoji.png`

### V5: No Regressions

1. On the OSS compliance page, verify the filter tabs ("Open issues", "Critical", "Warnings", etc.) are present and clickable.
2. Navigate to the Dashboard page and verify the "Active Batches", "Running Steps", and "Completed This Week" cards still render correctly.
3. Check the browser console for any new JavaScript errors (use `playwright-cli console` if available, or note absence of error indicators).
4. **Screenshot**: `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00045/evidences/post/I-00045_v5_no_regressions.png`

---

## Pass Criteria

All V1–V5 must pass. Any failure requires calling `iw step-fail` with a specific reason.

For ENV_DATA_MISSING (e.g., no OssScan row in E2E DB):
```bash
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "ENV_DATA_MISSING: V1 requires OssScan with summary_json — add ai-dev/active/I-00045/e2e_fixtures/001_oss_scan_seed.py" \
  --report ai-dev/active/I-00045/reports/I-00045_S11_BrowserVerification_Report.md
```

---

## Report

Write `ai-dev/active/I-00045/reports/I-00045_S11_BrowserVerification_Report.md` with:
- Pass/fail table for V1–V5
- The exact `$IW_BROWSER_BASE_URL` used
- List of screenshots captured
- Any issues found with file:line references
- "No regressions observed" subsection

Then call:
```bash
# On pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00045/reports/I-00045_S11_BrowserVerification_Report.md

# On failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<specific reason>" \
  --report ai-dev/active/I-00045/reports/I-00045_S11_BrowserVerification_Report.md
```

---

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00045",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "No raw JSON in pill", "status": "pass|fail", "screenshot": "evidences/post/I-00045_v1_no_raw_json.png", "notes": ""},
    {"id": "V2", "name": "OSS STATUS heading is link", "status": "pass|fail", "screenshot": "evidences/post/I-00045_v2_heading_link.png", "notes": ""},
    {"id": "V3", "name": "Stale banner no border", "status": "pass|fail|n/a", "screenshot": "evidences/post/I-00045_v3_stale_no_border.png", "notes": ""},
    {"id": "V4", "name": "CSS dots not emoji", "status": "pass|fail", "screenshot": "evidences/post/I-00045_v4_no_emoji.png", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "screenshot": "evidences/post/I-00045_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
