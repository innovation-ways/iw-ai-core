# Browser Verification Prompt: F-00058-S16-BrowserVerification

**Work Item**: F-00058 -- OSS compliance dashboard view + status pill
**Step**: S16
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:3100`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md` -- the design document
- `ai-dev/active/F-00058/evidences/pre/F-00058-project-page-before.png` -- pre-state
- Files modified by S01..S10:
  - `orch/db/migrations/versions/{hash}_add_project_oss_job.py`
  - `orch/db/models.py`
  - `dashboard/services/oss_service.py`
  - `dashboard/routers/oss.py`
  - `dashboard/app.py`
  - `dashboard/templates/pages/project/oss.html`
  - `dashboard/templates/fragments/oss_*.html` (7 fragments)
  - Modified project-page header template + project-tabs partial

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S16_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/F-00058/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs (e10, e12, ...)
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/F-00058/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack starts with a **fresh PostgreSQL** that has the project's schema and migrations applied, plus the baseline seed in `scripts/e2e_seed.py` (project row, architecture map, three demo work items). It does **not** mirror the production database.

For this feature, verifications require:

- At least one project with `oss_enabled=false` (for AC2 / Install flow).
- At least one project with `oss_enabled=true` + no prior scans (for gray-pill state).
- At least one project with `oss_enabled=true` + one complete `oss_scan` row with `pill_color='yellow'` and a handful of `oss_finding` + `oss_tool_run` rows (for AC1 / AC6).
- At least one project whose latest `oss_scan.head_sha` differs from current HEAD (for AC5 / stale).

If the baseline seed does not cover these, add a fixture at:

```
ai-dev/active/F-00058/e2e_fixtures/001_oss_seed.py
```

Exporting `def seed(db: Session) -> None`, idempotent. Required if any of V1..V7 hit an empty state on the first run.

## Verification Steps

### V1: OSS Status frame renders on every project page (AC1, AC7)

1. Navigate to `$IW_BROWSER_BASE_URL/projects/<oss-enabled-project-with-yellow-scan>/code`.
2. **Verify:** an OSS Status frame is visible immediately underneath the Git Status frame, showing a 🟡 yellow pill with summary text (e.g. "3 warnings, 0 blockers").
3. Navigate to `/tests`, `/quality`, `/documentation`, `/oss` for the same project.
4. **Verify:** the OSS Status frame appears in the same slot (underneath Git Status) on every page.
5. **Screenshot:** `ai-dev/active/F-00058/evidences/post/F-00058_v1_frame_on_each_page.png` (full-page capture of `/code` page).

### V2: OSS disabled state (AC2)

1. Navigate to `$IW_BROWSER_BASE_URL/projects/<oss-disabled-project>/code`.
2. **Verify:** the OSS Status frame shows "Install OSS" CTA; no pill; no "OSS" tab in the project tab row.
3. Click the "Install OSS" button.
4. **Verify:** a modal opens listing Tier-1 tools; each missing tool has a copy-able install command.
5. **Screenshot:** `ai-dev/active/F-00058/evidences/post/F-00058_v2_install_modal.png`.

### V3: Enable flow flips flag + shows gray pill (AC2)

1. Continuing from V2, close the modal (if tools are present) or simulate install complete, then click "Enable OSS".
2. **Verify:** modal dismisses; OSS Status frame switches to a ⚫ gray pill with "not yet scanned" text; a new "OSS" tab appears in the project tab row.
3. Navigate to `/oss` via the new tab.
4. **Verify:** the OSS view page loads with the Scan / Prepare / Publish action row, each with its collapsible "Run it yourself" CLI block.
5. **Screenshot:** `ai-dev/active/F-00058/evidences/post/F-00058_v3_enabled_gray_pill.png`.

### V4: Scan + SSE progress (AC3)

1. On the `/oss` view (from V3), click "Scan".
2. **Verify:** a progress row appears with live stdout lines streaming in via SSE.
3. Wait for completion (≤60s in E2E).
4. **Verify:** the progress row is replaced by the results tree; the pill transitions from gray to green/yellow/red per the scan verdict.
5. **Screenshot:** `ai-dev/active/F-00058/evidences/post/F-00058_v4_scan_complete.png`.

### V5: Results tree is understandable (AC6)

1. On the completed scan view (from V4), expand at least two domain cards.
2. **Verify:** each domain card shows finding count by severity, collapsible detail rows, and at least one `oss_tool_run_card` inside with the tool name, version badge, runtime, and verdict badge.
3. **Screenshot:** `ai-dev/active/F-00058/evidences/post/F-00058_v5_results_tree.png`.

### V6: Prepare with CLI block (AC4)

1. On the `/oss` view, click "Prepare for OSS".
2. **Verify:** a progress row appears streaming the prepare job's stdout; on completion it reports the prep branch name and staged-file count.
3. **Verify:** underneath the Prepare button, the "Run it yourself" collapsible is present and, when expanded, shows the exact `uv run iw oss prepare --project <id>` command with a copy button.
4. **Verify:** the developer's current working tree (if inspectable via any dashboard view that surfaces git state) is NOT modified — the run happened in a throwaway worktree.
5. **Screenshot:** `ai-dev/active/F-00058/evidences/post/F-00058_v6_prepare_with_cli_block.png`.

### V7: Stale banner on HEAD advance (AC5)

1. Navigate to the project seeded with an `oss_scan` whose `head_sha` differs from live HEAD.
2. **Verify:** a "scan is stale: HEAD has changed" banner appears at the top of the `/oss` view.
3. **Verify:** the pill color reflects the last scan's verdict but is annotated with a ⚠ icon.
4. **Screenshot:** `ai-dev/active/F-00058/evidences/post/F-00058_v7_stale_banner.png`.

### V8: No Regressions

1. Revisit `/code`, `/tests`, `/quality`, `/documentation` for a project with `oss_enabled=true`.
2. **Verify:** each page renders without console errors; the Git Status frame is in its original position; the OSS Status frame appears underneath consistently.
3. Revisit the project list / dashboard home.
4. **Verify:** no console errors; no unexpected visual changes.
5. **Screenshot:** `ai-dev/active/F-00058/evidences/post/F-00058_v8_no_regressions.png`.

## Pass Criteria

All V1..V8 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** -- the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the page rendered cleanly with HTTP 200 but showed an empty-state message because the E2E DB lacks the seed the verification expects. Prefix the reason with `ENV_DATA_MISSING:` so the daemon recognises the class; the fix path is to add a fixture, not to retry.

## Report

After verification, write `ai-dev/active/F-00058/reports/F-00058_S16_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V8.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured.
- A **No regressions observed** subsection covering the adjacent flows tested in V8.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00058/reports/F-00058_S16_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00058/reports/F-00058_S16_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "F-00058",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "frame on each page", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "disabled state + install modal", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "enable flow", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "scan + SSE", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "results tree", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "prepare + CLI block", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "stale banner", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V8", "name": "no regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed. `fail` on any failure.
- `base_url_used`: The concrete URL the agent actually hit.
- `console_errors_observed`: Any console errors seen during any V(n), even if the verification otherwise passed. A non-empty list on a passing run should be flagged in the report.
