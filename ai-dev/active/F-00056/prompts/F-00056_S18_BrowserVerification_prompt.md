# Browser Verification Prompt: F-00056-S18-BrowserVerification

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step**: S18
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser`
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- the design document
- Files modified by F-00056 implementation steps:
  - `orch/db/models.py`
  - `orch/db/migrations/versions/<rev>_add_fix_summary_to_fix_cycles.py`
  - `orch/daemon/execution_report.py`
  - `orch/daemon/batch_manager.py`
  - `orch/daemon/fix_cycle.py`
  - `orch/cli/item_commands.py`
  - `orch/cli/main.py`
  - `dashboard/routers/items.py`
  - `dashboard/templates/fragments/item_execution_report.html`
  - `dashboard/templates/pages/project/item_execution_report.html`
  - `dashboard/templates/pages/project/item_detail.html`
  - `dashboard/static/execution_report.css` (if created)
  - `ai-dev/templates/CodeReview_FIX_Prompt_Template.md`
  - `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md`
  - `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md`

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S18_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/F-00056/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials if the dashboard requires auth. If the IW AI Core dashboard in the worktree does not require login (per `dashboard/CLAUDE.md`), skip the login block; otherwise:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:

1. Always `snapshot` before `fill` / `click` to read current element refs. Do not reuse refs from prior pages.
2. Wait for navigation/transitions to settle between steps.
3. Screenshots go under `ai-dev/active/F-00056/evidences/post/` with descriptive filenames.

## Verification Steps

### V1: Execution Report tab loads on F-00055 and shows the hotspot summary

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/F-00055`.
2. Click the "Execution Report" tab in the tab bar — this tab was added by F-00056 and is the primary surface under verification.
3. **Verify:** the tab content contains the summary card with verdict "✓ Completed" and a retry-hotspot list that includes text matching **"S13"** with "× 3", **"S10"** with "× 2", and **"S16"** with "× 2" (or matching the actual F-00055 pattern documented in its execution report markdown file).
4. **Screenshot:** `ai-dev/active/F-00056/evidences/post/F-00056_v1_tab_summary_card.png`.

### V2: Gantt chart renders retry segments

1. On the same page, scroll to the Gantt section.
2. **Verify:** the row labeled "S13 ruff lint" (or equivalent label) contains at least four distinct rectangular segments (three retry-colored + one completed-colored). The row labeled "S10" contains at least two segments. The row labeled "S16" contains at least two segments.
3. **Verify:** color of the final segment in each retry row is emerald/green (`#10b981`), and the preceding segments are amber (`#f59e0b`). Inspect via DOM snapshot (classes `gantt-bar--retry` and `gantt-bar--completed`).
4. **Screenshot:** `ai-dev/active/F-00056/evidences/post/F-00056_v2_gantt_retry_segments.png`.

### V3: Timeline accordion expands and shows fix-cycle placeholder

1. Scroll to the "Retry Timeline" section.
2. Click the `<summary>` for the S13 entry — this expands the accordion.
3. **Verify:** the expanded body contains per-run entries and a blockquote. For F-00055 (backfilled, pre-F-00056 data), the blockquote MUST read in italics **"no fix summary captured (pre-F-00056)"**.
4. **Screenshot:** `ai-dev/active/F-00056/evidences/post/F-00056_v3_timeline_accordion_placeholder.png`.

### V4: Standalone deep-link page works

1. Navigate directly to `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/F-00055/execution-report` in a fresh page context.
2. **Verify:** page loads with HTTP 200, wrapped in the standard dashboard chrome (header, navigation). The summary card, Gantt, and timeline from V1-V3 are all visible.
3. **Verify:** the browser URL in the address bar matches the requested URL (no redirect).
4. **Screenshot:** `ai-dev/active/F-00056/evidences/post/F-00056_v4_standalone_page.png`.

### V5: Markdown file exists for F-00055 and two priors

1. Read S09's report `notes` for the three backfilled items and their resolved paths (each is in `ai-dev/active/<id>/` or `ai-dev/archive/<id>/` depending on whether the item was already archived at backfill time). Via shell: `ls -la <resolved_path>` for each — confirm file exists at the path S09 recorded.
2. For each of the three items, confirm the resolved `<id>_execution_report.md` file is present on disk.
3. **Verify:** each file is non-empty and contains the literal strings "Retry Hotspots", "Step Timeline", "Fix Cycles".
4. **Screenshot:** not required for this V; include a shell-output paste in the report instead.

### V6: No Regressions on existing tabs

1. Return to `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/F-00055`.
2. Click each existing tab in order: Overview, Design Doc, Reports, Artifacts, Evidences, Logs, Fix Cycles.
3. **Verify:** each tab loads with no HTTP error and renders content consistent with its pre-F-00056 behavior (compare against the pre-implementation screenshot at `ai-dev/active/F-00056/evidences/pre/F-00056-item-detail-before.png` for the default tab).
4. **Verify:** no new console errors appeared on any page visited during V1..V5. Inspect the playwright-cli console log output.
5. **Screenshot:** `ai-dev/active/F-00056/evidences/post/F-00056_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Any failure (including partial or ambiguous results) requires calling `iw step-fail` with a specific reason and an attached screenshot.

## Report

After verification, write `ai-dev/active/F-00056/reports/F-00056_S18_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V6.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V6.

Then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00056/reports/F-00056_S18_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00056/reports/F-00056_S18_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S18",
  "agent": "qv-browser",
  "work_item": "F-00056",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Execution Report tab loads on F-00055", "status": "pass|fail", "screenshot": "ai-dev/active/F-00056/evidences/post/F-00056_v1_tab_summary_card.png", "notes": ""},
    {"id": "V2", "name": "Gantt chart renders retry segments", "status": "pass|fail", "screenshot": "ai-dev/active/F-00056/evidences/post/F-00056_v2_gantt_retry_segments.png", "notes": ""},
    {"id": "V3", "name": "Timeline accordion expands and shows fix-cycle placeholder", "status": "pass|fail", "screenshot": "ai-dev/active/F-00056/evidences/post/F-00056_v3_timeline_accordion_placeholder.png", "notes": ""},
    {"id": "V4", "name": "Standalone deep-link page works", "status": "pass|fail", "screenshot": "ai-dev/active/F-00056/evidences/post/F-00056_v4_standalone_page.png", "notes": ""},
    {"id": "V5", "name": "Markdown files exist for backfilled items", "status": "pass|fail", "screenshot": "", "notes": "shell output in report"},
    {"id": "V6", "name": "No regressions on existing tabs", "status": "pass|fail", "screenshot": "ai-dev/active/F-00056/evidences/post/F-00056_v6_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
