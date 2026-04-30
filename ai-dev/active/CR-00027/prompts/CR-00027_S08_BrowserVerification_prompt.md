# Browser Verification Prompt: CR-00027-S08-BrowserVerification

**Work Item**: CR-00027 -- Dashboard Sidebar Nav: Collapsible Section Headers
**Step**: S08
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var.

Do NOT run `make dev`, `docker compose`, `playwright install`, or `agent-browser`. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/CR-00027/CR-00027_CR_Design.md` — the design document
- `dashboard/templates/base.html` — the modified sidebar template

## Output Files

- `ai-dev/active/CR-00027/reports/CR-00027_S08_BrowserVerification_Report.md`
- `ai-dev/active/CR-00027/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

No login is required for the dashboard (unauthenticated). Navigate directly.

## Verification Steps

### V1: Section headers are visually distinct

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. Take a snapshot and inspect the sidebar — locate the "Projects" and "System" labels.
3. **Verify:** Both labels appear with heavier weight (bold/semibold) and a noticeably brighter/different color compared to the nav items beneath them (e.g., project sub-links like "Dashboard", "Queue"). Each label has a chevron icon.
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/CR-00027/evidences/post/CR-00027_v1_headers_distinct.png`

### V2: Both sections start expanded

1. Clear localStorage to simulate first visit: use `playwright-cli` evaluate or simply ensure a fresh browser context (the isolated stack uses a fresh context by default).
2. Navigate to `$IW_BROWSER_BASE_URL/`.
3. **Verify:** Both the project list (at least one project entry or "No projects registered") and all System links ("Running Tasks", "Worktree Health", etc.) are visible in the sidebar.
4. **Screenshot:** `ai-dev/active/CR-00027/evidences/post/CR-00027_v2_both_expanded.png`

### V3: Projects section collapses on click

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. Take a snapshot to find the "Projects" summary element ref, then click it.
3. **Verify:** The project list area is no longer visible (section is collapsed). The chevron has rotated to indicate collapsed state.
4. **Screenshot:** `ai-dev/active/CR-00027/evidences/post/CR-00027_v3_projects_collapsed.png`

### V4: Projects section expands again on click

1. Continuing from V3 (Projects is collapsed).
2. Click the "Projects" header again.
3. **Verify:** The project list is visible again (section expanded). Chevron has rotated back.
4. **Screenshot:** `ai-dev/active/CR-00027/evidences/post/CR-00027_v4_projects_expanded.png`

### V5: System section collapses and expands

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. Click the "System" header.
3. **Verify:** System links ("Running Tasks", "Worktree Health", etc.) are hidden.
4. Click "System" again.
5. **Verify:** System links are visible again.
6. **Screenshot:** `ai-dev/active/CR-00027/evidences/post/CR-00027_v5_system_toggle.png`

### V6: localStorage state persists across navigation

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. Collapse the "System" section by clicking its header.
3. Navigate to `$IW_BROWSER_BASE_URL/system/status` (a different page).
4. **Verify:** The "System" section is still collapsed after navigation. The "Projects" section is still expanded.
5. **Screenshot:** `ai-dev/active/CR-00027/evidences/post/CR-00027_v6_state_persists.png`

### V7: No Regressions

1. Navigate to a project page (e.g. `$IW_BROWSER_BASE_URL/`) and verify:
   - Active link highlighting still works (current page link is highlighted)
   - The htmx-loaded project list renders correctly inside the expanded Projects section
   - The worktree badge polling `hx-get="/system/nav/worktree-badge"` element is present in the DOM
2. Verify no JavaScript console errors appeared on any page visited during V1–V6.
3. **Screenshot:** `ai-dev/active/CR-00027/evidences/post/CR-00027_v7_no_regressions.png`

## Pass Criteria

All V1–V7 must pass. Any failure requires calling `iw step-fail`.

## Report

Write `ai-dev/active/CR-00027/reports/CR-00027_S08_BrowserVerification_Report.md` then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00027/reports/CR-00027_S08_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00027/reports/CR-00027_S08_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "qv-browser",
  "work_item": "CR-00027",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "headers_distinct", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "both_expanded", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "projects_collapsed", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "projects_expanded", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "system_toggle", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "state_persists", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "no_regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
