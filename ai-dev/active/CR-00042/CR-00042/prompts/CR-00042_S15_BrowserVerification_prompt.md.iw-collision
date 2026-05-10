# Browser Verification Prompt: CR-00042-S15-BrowserVerification

**Work Item**: CR-00042 — Fix Broken "Open full docs" Links in Help Popups
**Step**: S15
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does not touch migrations.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/CR-00042/CR-00042_CR_Design.md` — acceptance criteria AC1–AC5
- `dashboard/routers/system.py` — new `/system/docs/{doc_slug}` route
- `dashboard/routers/help.py` — `_SLUG_TO_DOC` mapping
- `dashboard/templates/_partials/help/*.html` — updated partials

## Output Files

- `ai-dev/active/CR-00042/reports/CR-00042_S15_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/CR-00042/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in with the provided credentials (snapshot first to find field refs).

## Verification Steps

### V1: Help popup "Open full docs" link resolves (not 404)

1. Navigate to `$IW_BROWSER_BASE_URL/system/status`.
2. Click the "?" help button — this opens the help popup for the System Status page.
3. Snapshot the page to locate the "Open full docs →" link ref.
4. Verify the link has an `href` containing `/system/docs/` (not `/docs/IW_AI_Core`).
5. Click "Open full docs →".
6. **Verify:** The browser navigates to a page with HTTP 200, displaying rendered content (headings visible, not raw `#` markdown text). The URL contains `/system/docs/IW_AI_Core_DB_Setup`.
7. **Screenshot:** `ai-dev/active/CR-00042/evidences/post/CR-00042_v1_docs_link_resolves.png`

### V2: Rendered doc page displays styled content

1. The page from V1 should be open at `/system/docs/IW_AI_Core_DB_Setup`.
2. Snapshot the page.
3. **Verify:** The page contains readable headings and text — not a wall of raw markdown. The page has a back button (`← Back`). The page extends the dashboard base layout (nav sidebar visible).
4. **Screenshot:** `ai-dev/active/CR-00042/evidences/post/CR-00042_v2_rendered_doc_styled.png`

### V3: A second help popup uses correct link (different slug)

1. Navigate to `$IW_BROWSER_BASE_URL` (projects landing page or any project's queue page).
2. Open the help popup for that page.
3. **Verify:** The "Open full docs →" link href contains `/system/docs/` (not a legacy `/docs/IW_AI_Core` path).
4. Click the link and verify it resolves to HTTP 200 with rendered content.
5. **Screenshot:** `ai-dev/active/CR-00042/evidences/post/CR-00042_v3_second_popup_link.png`

### V4: Direct access to `/system/docs/{slug}` works

1. Navigate to `$IW_BROWSER_BASE_URL/system/docs/IW_AI_Core_Daemon_Design`.
2. **Verify:** HTTP 200, page renders with at least one heading visible.
3. Navigate to `$IW_BROWSER_BASE_URL/system/docs/nonexistent_slug`.
4. **Verify:** The page shows an error or 404 — does NOT show file content or a stack trace.
5. **Screenshot:** `ai-dev/active/CR-00042/evidences/post/CR-00042_v4_direct_access.png`

### V5: No Regressions

1. Navigate to several other dashboard pages (queue, batches, system status) and verify each page loads correctly.
2. Open the help popup on each page visited and verify it still appears and closes normally.
3. Verify no new console errors appeared on any page visited during V1–V4.
4. **Screenshot:** `ai-dev/active/CR-00042/evidences/post/CR-00042_v5_no_regressions.png`

## Pass Criteria

All V1–V5 must pass. See the base template for failure classification (CODE_DEFECT / ENV_DATA_MISSING / SPEC_MISMATCH).

## Report

Write `ai-dev/active/CR-00042/reports/CR-00042_S15_BrowserVerification_Report.md`, then:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00042/reports/CR-00042_S15_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short specific reason>" \
  --report ai-dev/active/CR-00042/reports/CR-00042_S15_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "CR-00042",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Help popup link resolves", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Rendered doc page styled", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Second popup correct link", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Direct access + 404 safety", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
