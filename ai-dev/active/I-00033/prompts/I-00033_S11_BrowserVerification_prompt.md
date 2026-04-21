# Browser Verification Prompt: I-00033-S11-BrowserVerification

**Work Item**: I-00033 — Code view layout bugs: undismissible "Last run" banner, misplaced scrollbar, wasted space on chat collapse
**Step**: S11
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no `localhost:3100`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, `make dashboard-start`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00033/I-00033_Issue_Design.md` -- the design document (especially the "Browser Verification Script" section)
- `ai-dev/active/I-00033/evidences/pre/I-00033-code-view-initial.png` -- pre-fix screenshot
- `dashboard/templates/fragments/code_job_report.html`
- `dashboard/templates/project_code.html`
- `dashboard/templates/fragments/code_architecture_view.html`
- `dashboard/static/chat/panel.js`
- `dashboard/templates/chat/panel.html`

## Output Files

- `ai-dev/active/I-00033/reports/I-00033_S11_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00033/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the dashboard does not require login, skip the login step. Otherwise:

```bash
playwright-cli snapshot                       # get accessible element refs (e10, e12, ...)
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

(The iw-ai-core dashboard has no login today — if `$IW_BROWSER_BASE_URL` loads directly into the project list, skip login and proceed.)

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00033/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack starts with a **fresh PostgreSQL** that has the project's schema and migrations applied, plus the baseline seed in `scripts/e2e_seed.py`. It does **not** mirror the production database.

These verifications require:

- An `iw-ai-core` project row (in baseline seed).
- At least one completed `CodeIndexJob` with `completed_at` within the last hour (so `last_completed_recent` is True and the banner renders).

If the baseline seed does NOT include a recent `CodeIndexJob`, add a fixture file:

```
ai-dev/active/I-00033/e2e_fixtures/001_code_index_job_recent.py
```

The file must export `def seed(db: Session) -> None` and be idempotent. It inserts a `CodeIndexJob` with:
- `project_id = "iw-ai-core"`
- `status = "completed"`
- `completed_at = datetime.now(UTC) - timedelta(minutes=5)`
- `files_indexed = 10`, `chunks_created = 100`
- `llm_model`, `embed_model`, `provider` — any valid non-null values

If your verifications cannot be satisfied with seed data alone (e.g., the architecture map doesn't exist in the fresh DB so the page renders an empty state), call `iw step-fail` with reason prefixed `ENV_DATA_MISSING:` (see Pass Criteria) — the daemon recognises this as an environment gap, not a code defect, and skips the fix cycle.

## Verification Steps

### V1: Bug 1 — "Last run" banner is dismissible and persists per-job-id

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/code`.
2. **Snapshot** to locate the "Last run" banner. It should be visible with the text `Last run · <duration> · <files> files · <chunks> chunks`.
3. **Verify** the banner root has id `code-last-run-banner` and is visible.
4. Locate the close button via `playwright-cli snapshot` (look for `aria-label="Dismiss last-run banner"`). Click it.
5. **Verify** the banner disappears immediately (snapshot should no longer show it, or `run-code` check: `document.getElementById('code-last-run-banner')` is either null or has `display: none`).
6. **Screenshot:** `ai-dev/active/I-00033/evidences/post/I-00033_v1a_banner_dismissed.png`.
7. Reload the page (`playwright-cli reload`). Wait a moment.
8. **Snapshot** again. The banner MUST NOT reappear (localStorage persistence).
9. **Screenshot:** `ai-dev/active/I-00033/evidences/post/I-00033_v1b_banner_hidden_after_reload.png`.
10. Simulate a new job via `playwright-cli run-code "localStorage.setItem('iw_code_lastrun_dismissed:iw-ai-core', 'old-job-id-that-does-not-match')"` and reload. The banner MUST reappear (the stored id no longer matches the current job's id).
11. **Screenshot:** `ai-dev/active/I-00033/evidences/post/I-00033_v1c_banner_returns_on_new_job.png`.

### V2: Bug 2 — Scrollbar sits inside the Architecture card, not at the column edge

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/code`.
2. Use `playwright-cli run-code` to walk up from `.prose-doc` and find the nearest ancestor with `overflowY: auto`:
   ```javascript
   (function(){
     var p = document.querySelector('.prose-doc');
     var e = p;
     while (e) {
       if (getComputedStyle(e).overflowY === 'auto') return (e.id || 'noId') + '|' + e.className;
       e = e.parentElement;
     }
     return 'NONE';
   })()
   ```
3. **Verify** the returned element's id is NOT `code-content-root` AND the className contains `bg-card` (the Architecture card).
4. Scroll the content: `playwright-cli run-code "document.querySelector('.bg-card').scrollTop = 400"` (or whichever selector is the actual scroll container from step 2).
5. **Screenshot:** `ai-dev/active/I-00033/evidences/post/I-00033_v2_scrollbar_inside_card.png`. The screenshot should show a scrollbar inside the card's right border, with a visible gap between the card and the chat panel.

### V3: Bug 3 — Collapsing the chat sets `--chat-width` to 48px and reclaims space

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/code`.
2. Read the initial state:
   ```javascript
   (function(){
     var w = getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim();
     var cw = document.getElementById('code-content-root').getBoundingClientRect().width;
     return w + '|' + cw;
   })()
   ```
   Record the initial `--chat-width` (expected ~400px) and the code-content-root width.
3. **Snapshot** to locate the chat-collapse button (`#chat-collapse-btn`, aria-label "Collapse chat panel (Cmd+\\)"). Click it.
4. Re-read the same values via `run-code`.
5. **Verify** `--chat-width` equals `"48px"` (exact string match).
6. **Verify** the code-content-root width GREW by approximately `initial_chat_width - 48` pixels (allow ~20px slack for gap/border rounding).
7. **Screenshot:** `ai-dev/active/I-00033/evidences/post/I-00033_v3a_chat_collapsed.png`. Should show the chat as a thin 48px vertical rail with only an expand arrow visible.
8. Click the collapse button again (to expand).
9. **Verify** `--chat-width` is restored to the saved width (read `localStorage.getItem('iw_chat_width')` — default `"400"`).
10. **Screenshot:** `ai-dev/active/I-00033/evidences/post/I-00033_v3b_chat_expanded.png`.

### V4: No Regressions

1. Revisit adjacent flows:
   - Open a module from the Modules list — the detail panel renders in `#code-detail-panel`.
   - Ask a question in the chat composer — the message appears in `#chat-messages`.
   - Resize the chat panel via the resize handle (`#chat-resize-handle`) — width updates, persists on mouseup.
2. **Verify** no new console errors appeared on any page visited during V1..V3. Check via `playwright-cli console` — the output should contain no entries with `level: error` that were not already present on the pre-V1 page load.
3. **Screenshot:** `ai-dev/active/I-00033/evidences/post/I-00033_v4_no_regressions.png`.

### V5: Mobile drawer unchanged (optional, environmental)

If the E2E stack supports viewport resizing:

1. `playwright-cli resize 800 600` — mobile-ish viewport.
2. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/code`.
3. **Verify** the chat drawer is off-canvas (fixed positioning, translate-x-full) and opens/closes via the `#chat-drawer-open` button — behavior unchanged from pre-S01.
4. **Screenshot:** `ai-dev/active/I-00033/evidences/post/I-00033_v5_mobile_drawer.png`.

If the environment does not support resize, skip V5 and note in the report.

## Pass Criteria

All V1..V4 must pass. V5 is optional (environmental). Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** -- the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the page rendered cleanly with HTTP 200 but showed an empty-state message because the E2E DB lacks the historical rows the verification expects. Prefix the reason with `ENV_DATA_MISSING:` so the daemon recognises the class:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 expects a recent CodeIndexJob row for iw-ai-core — add ai-dev/active/I-00033/e2e_fixtures/001_code_index_job_recent.py" \
    --report ai-dev/active/I-00033/reports/I-00033_S11_BrowserVerification_Report.md
  ```

## Report

After verification, write `ai-dev/active/I-00033/reports/I-00033_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V4 (and V5 if attempted).
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V4.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00033/reports/I-00033_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00033/reports/I-00033_S11_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00033",
  "overall_status": "pass|fail",
  "base_url_used": "<copy $IW_BROWSER_BASE_URL at run time>",
  "verifications": [
    {"id": "V1", "name": "Banner dismissal + per-job-id persistence", "status": "pass|fail", "screenshot": "evidences/post/I-00033_v1a_banner_dismissed.png", "notes": ""},
    {"id": "V2", "name": "Scroll container is the Architecture card", "status": "pass|fail", "screenshot": "evidences/post/I-00033_v2_scrollbar_inside_card.png", "notes": ""},
    {"id": "V3", "name": "Chat collapse sets --chat-width=48px and reclaims space", "status": "pass|fail", "screenshot": "evidences/post/I-00033_v3a_chat_collapsed.png", "notes": ""},
    {"id": "V4", "name": "No regressions (module detail, chat send, resize handle)", "status": "pass|fail", "screenshot": "evidences/post/I-00033_v4_no_regressions.png", "notes": ""},
    {"id": "V5", "name": "Mobile drawer unchanged (optional)", "status": "pass|fail|skip", "screenshot": "evidences/post/I-00033_v5_mobile_drawer.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V1..V4 passed. `fail` on any failure. V5 is optional.
- `base_url_used`: The concrete URL the agent actually hit -- used by reviewers to confirm the worktree stack (not the dev server) was tested.
- `console_errors_observed`: Any console errors seen during any V(n), even if the verification otherwise passed. A non-empty list on a passing run should be flagged in the report.
