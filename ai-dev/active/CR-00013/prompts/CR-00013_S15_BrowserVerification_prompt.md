# Browser Verification Prompt: CR-00013-S15-BrowserVerification

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Step**: S15
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no `localhost:3100`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` -- the design document
- `dashboard/templates/base.html`
- `dashboard/static/styles.css` (prebuilt CSS)
- `dashboard/templates/components/libs/*.html` (lazy-loaded lib includes)
- `dashboard/routers/worktrees.py`, `dashboard/routers/system.py`, `dashboard/routers/daemon_control.py`
- `dashboard/routers/projects.py`, `dashboard/routers/project_dashboard.py`, `dashboard/routers/batches.py`, `dashboard/routers/items.py`, `dashboard/routers/running.py`
- `orch/db/session.py`, `orch/config.py`
- `dashboard/app.py`
- `ai-dev/active/CR-00013/evidences/pre/*.png` -- pre-change screenshots to compare against

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S15_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00013/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00013/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack starts with a **fresh PostgreSQL** that has the project's schema and migrations applied, plus the baseline seed in `scripts/e2e_seed.py`. It does **not** mirror the production database.

If a verification requires historical data (multiple projects, many batches/items to stress the formerly-N+1 routes), add a fixture file:

```
ai-dev/active/CR-00013/e2e_fixtures/001_perf_dataset.py
```

Export `def seed(db: Session) -> None` — idempotent — to create ≥5 projects, ≥10 batch items per active batch, and ≥10 steps per item, so the bounded-query and cache verifications are meaningful.

If a verification can't be satisfied by seed + fixtures, call `iw step-fail` with reason prefixed `ENV_DATA_MISSING:`.

## Verification Steps

### V1: Prebuilt Tailwind CSS in place (AC6)

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. Take a full-page screenshot and inspect the page source (`playwright-cli snapshot`) to confirm:
   - The `<script src="https://cdn.tailwindcss.com">` tag is **absent**.
   - A `<link rel="stylesheet" href="/static/styles.css">` is present.
3. **Verify:** the rendered layout matches `ai-dev/active/CR-00013/evidences/pre/01-project-selector.png` visually (same sidebar width, same card spacing, same colors in both light and dark mode).
4. **Screenshot:** `ai-dev/active/CR-00013/evidences/post/CR-00013_v1_prebuilt_css.png`.

### V2: Self-hosted Inter font (AC6)

1. On the same page, inspect the DOM head.
2. **Verify:** no `fonts.googleapis.com` or `fonts.gstatic.com` link is present. A `@font-face` declaration for Inter is loaded (check computed `font-family` of `body` resolves to `Inter`).
3. **Screenshot:** `ai-dev/active/CR-00013/evidences/post/CR-00013_v2_inter_font.png`.

### V3: Sidebar worktree badge cached, fast (AC1, AC4)

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. Observe the sidebar under "System" → "Worktree Health". The badge (`worktree_nav_badge`) must render within the visible loading interval without causing the page to hang.
3. Navigate to another page (e.g., `/system/status`) and back. The badge should remain consistent and render within 50 ms (observable as "no visible re-loading flash").
4. **Verify:** page-to-page navigation completes quickly with no multi-second delay. Observe in the browser DevTools Network panel (if accessible via `playwright-cli`) that `/system/nav/worktree-badge` completes in <100 ms for at least the second hit.
5. **Screenshot:** `ai-dev/active/CR-00013/evidences/post/CR-00013_v3_badge_cached.png`.

### V4: Project selector bounded queries (AC3)

1. Navigate to `$IW_BROWSER_BASE_URL/`.
2. **Verify:** with ≥5 projects seeded, the page renders fully in under 1 second. All project cards show their stats correctly.
3. **Screenshot:** `ai-dev/active/CR-00013/evidences/post/CR-00013_v4_project_selector.png`.
4. Compare with `evidences/pre/01-project-selector.png` — visual parity.

### V5: Project dashboard + batch detail + item detail (AC3)

1. Click into one project.
2. Click into one active batch (or navigate to a batch with ≥10 items if seeded).
3. Click into one work item, then cycle through its tabs (Design, Tests, Quality — whichever exist).
4. **Verify:** each page renders in under 1 second. Step list, test results, and quality panels populate correctly.
5. **Screenshot:** one per page — `CR-00013_v5a_project_dashboard.png`, `CR-00013_v5b_batch_detail.png`, `CR-00013_v5c_item_detail.png`.

### V6: System status and Running Tasks (AC3, AC4)

1. Navigate to `$IW_BROWSER_BASE_URL/system/status`.
2. **Verify:** page renders within 1 second on the second load (cache hit on git-stat reads). Project summaries populate correctly with branch names and ahead counts.
3. Navigate to `$IW_BROWSER_BASE_URL/system/running`. **Verify:** running + failed items list renders without delay.
4. **Screenshot:** `CR-00013_v6a_system_status.png`, `CR-00013_v6b_running_tasks.png`.
5. Compare with `evidences/pre/02-system-status.png` and `evidences/pre/03-running-tasks.png`.

### V7: Mermaid and Highlight.js still work on pages that use them (AC6, AC8)

1. Navigate to an item that has a design document with Mermaid diagrams (e.g., any archived F-00057 / F-00058 artifact rendering).
2. **Verify:** Mermaid diagrams render (SVG is present, not raw text). The page-specific `{% block head %}` include loaded Mermaid.
3. Navigate to a code-viewer page (code / diff page).
4. **Verify:** Highlight.js colorizes code blocks (`<span class="hljs-keyword">` etc. appear in DOM).
5. **Screenshot:** `CR-00013_v7a_mermaid.png`, `CR-00013_v7b_hljs.png`.

### V8: Daemon control doesn't block navigation (AC5)

1. Navigate to `$IW_BROWSER_BASE_URL/system/config` (or wherever the daemon controls live).
2. Click "Restart daemon" (or equivalent). While the restart is in progress, open a new tab and navigate to `$IW_BROWSER_BASE_URL/`.
3. **Verify:** the second tab loads without being blocked by the in-progress restart.
4. **Screenshot:** `CR-00013_v8_daemon_restart.png`.

### V9: No Regressions

1. Revisit project dashboard, item detail, and search. Confirm all interactions (click-through, search typing, tab switching, htmx fragment swaps) still work.
2. Verify no new console errors appeared on any page visited during V1..V8. Capture the console log.
3. **Screenshot:** `CR-00013_v9_no_regressions.png`.

## Pass Criteria

All V1..V9 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** -- HTTP error, console exception, wrong element rendered, broken layout. Normal `--reason`.
- **ENV_DATA_MISSING** -- HTTP 200 but empty-state because seed lacks data (e.g., no batches to exercise bounded-query verification). Prefix reason with `ENV_DATA_MISSING:` and add a fixture file.

## Report

After verification, write `ai-dev/active/CR-00013/reports/CR-00013_S15_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V9.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if root cause was investigated.
- List of screenshots under `evidences/post/`.
- A **No regressions observed** subsection covering adjacent flows.
- Observed timing data (from DevTools Network or playwright-cli timing output) for key routes.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00013/reports/CR-00013_S15_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00013/reports/CR-00013_S15_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "CR-00013",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Prebuilt Tailwind CSS", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Self-hosted Inter font", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Sidebar badge cached", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Project selector bounded queries", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Project/batch/item detail bounded queries", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "System status + Running tasks", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "Mermaid + Highlight.js still render", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V8", "name": "Daemon restart doesn't block nav", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V9", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
