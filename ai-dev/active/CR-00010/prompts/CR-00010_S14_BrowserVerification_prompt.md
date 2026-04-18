# Browser Verification Prompt: CR-00010-S14-BrowserVerification

**Work Item**: CR-00010 — Research items auto-complete without manual approval
**Step**: S14
**Agent**: qv-browser

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `localhost:5173`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment.

Do NOT run any of the following — they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make dashboard-start`, `make daemon-start`, `make test-e2e`, `make e2e-up`, or any `docker compose` command — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00010/CR-00010_CR_Design.md` — the design document
- `dashboard/routers/actions.py`
- `dashboard/routers/project_pages.py` (and any sibling batch-queue router modified by S03)
- `dashboard/templates/**` (all approve/unapprove render sites + batch-queue template)
- `orch/cli/item_commands.py`
- `orch/cli/doc_commands.py`
- `orch/cli/batch_commands.py`

## Output Files

- `ai-dev/active/CR-00010/reports/CR-00010_S14_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/CR-00010/evidences/post/` — screenshots

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials if the dashboard exposes an auth screen:

```bash
playwright-cli snapshot
# If a login form appears:
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

(The isolated dashboard stack may not require auth — if no login form appears, proceed directly.)

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions (htmx swaps) to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00010/evidences/post/` with descriptive filenames.

## Seed Data Setup

Before verification, create a research work item AND a non-research work item for comparison. Use the CLI (not the dashboard — we want to verify the CLI→dashboard flow):

```bash
# Reserve IDs
R_ID=$(uv run iw next-id --type research)
F_ID=$(uv run iw next-id --type feature)

# Register both
uv run iw register "$R_ID" "Test research for CR-00010 browser check" --type research
uv run iw register "$F_ID" "Test feature for CR-00010 browser check" --type feature

# Approve the feature (to populate the batch-queue list)
uv run iw approve "$F_ID"

echo "SEEDED: R=$R_ID  F=$F_ID"
```

Record the two IDs in the report — you will reference them in V1..V(n).

## Verification Steps

### V1: Research item detail page hides approve/unapprove (AC8)

1. Navigate to `$IW_BROWSER_BASE_URL/projects/iw-ai-core/items/$R_ID` (substitute `$R_ID` with the concrete ID from setup; substitute the project slug with whatever the isolated stack seeded — if `iw-ai-core` is not the active project, pick the seeded project and use it consistently in V1..V(n)).
2. Wait for the page to fully render.
3. **Verify:** no button, link, or form labeled "Approve" or "Unapprove" is present on the page. Snapshot and grep the accessibility tree.
4. **Verify:** an inline notice is visible containing the phrase "auto-complete" (case-insensitive) — it should mention that research items auto-complete when the research document is created. The exact wording from the design is `"Research items auto-complete when the research document is created via iw doc-update. They do not use the approval workflow."`.
5. **Verify:** the browser console has no errors.
6. **Screenshot:** `ai-dev/active/CR-00010/evidences/post/CR-00010_v1_research_detail_no_approve.png`.

### V2: Non-research item detail page still shows approve/unapprove (regression guard)

1. Register a second draft feature (or reuse the seeded `$F_ID` after manually reverting it to draft via `iw unapprove $F_ID`) and navigate to its detail page.
2. **Verify:** an "Approve" button or form is visible (the exact label depends on the template — accept any variant containing the word "Approve").
3. **Verify:** no research-specific notice is shown.
4. **Screenshot:** `ai-dev/active/CR-00010/evidences/post/CR-00010_v2_feature_detail_has_approve.png`.

### V3: Research item absent from batch-queue list (AC9)

1. Navigate to whichever page on the dashboard lists approved work items eligible for batching (likely `$IW_BROWSER_BASE_URL/projects/iw-ai-core/batches/new` or `$IW_BROWSER_BASE_URL/projects/iw-ai-core/queue` — snapshot the nav and pick the route named "Queue", "Batch Queue", or similar; if none is obvious, check the sidebar).
2. **Verify:** the approved feature `$F_ID` appears in the list.
3. **Verify:** the research item `$R_ID` does NOT appear in the list (it's in draft, and even if it were in approved the backend filter excludes it).
4. **Additional check (optional — do only if the dashboard exposes it):** manually set `$R_ID`'s status to `approved` via a direct SQL shell IF the stack provides one, to test the defense-in-depth backend filter. If no shell is exposed, skip this sub-check and rely on AC9's backend-query test from S05.
5. **Screenshot:** `ai-dev/active/CR-00010/evidences/post/CR-00010_v3_batch_queue_no_research.png`.

### V4: `iw doc-update` auto-completes research item, dashboard reflects the change (AC3)

1. Run the doc-update command from the shell:
   ```bash
   uv run iw doc-update "$R_ID" \
     --doc-type research \
     --title "Test research CR-00010 browser check" \
     --content "# Test research content for browser verification"
   ```
2. **Verify:** the CLI output JSON contains `"work_item_auto_completed": true`.
3. Back in the browser, navigate to `$IW_BROWSER_BASE_URL/projects/iw-ai-core/items/$R_ID` (refresh the page if it was already open).
4. **Verify:** the item's status is displayed as `completed` (or whatever the dashboard uses to render `WorkItemStatus.completed`).
5. **Verify:** the inline "research items auto-complete" notice may still be shown (informational) OR the approve/unapprove section remains hidden. Either is acceptable.
6. **Screenshot:** `ai-dev/active/CR-00010/evidences/post/CR-00010_v4_research_completed_after_doc_update.png`.

### V5: `iw approve` CLI error path (AC1, console-visible)

1. Reset a fresh research item for this check (or reuse the completed one):
   ```bash
   R2_ID=$(uv run iw next-id --type research)
   uv run iw register "$R2_ID" "Second test research" --type research
   ```
2. Attempt to approve it:
   ```bash
   uv run iw approve "$R2_ID"
   echo "exit code: $?"
   ```
3. **Verify:** the exit code is non-zero.
4. **Verify:** stderr (or stdout, whichever the command uses for errors — grep both) contains `Cannot approve research items`.
5. This V5 is a CLI-only check (no browser screenshot needed) but fold the result into the report to document the end-to-end user experience.

### V6: Dashboard approve route rejection (AC1 via HTTP)

1. If the dashboard exposes an approve button on the research item detail page under any non-default condition (e.g., admin mode, override), confirm it is disabled. If no button exists at all (per V1), this check is covered by V1 and can be skipped — record "covered by V1" in the report.
2. Alternatively, POST directly to the approve route via the browser's fetch API (use `playwright-cli evaluate` if supported) and confirm the server returns a 4xx or htmx-error response. This is an optional hardening check — skip if the CLI surface is already verified.
3. **Screenshot (if applicable):** `ai-dev/active/CR-00010/evidences/post/CR-00010_v6_route_rejection.png`.

### V(n): No Regressions

1. Verify non-research items still behave normally:
   - `$F_ID`'s detail page shows the full approve/unapprove workflow (covered by V2).
   - An approved non-research item still appears in the batch-queue list (covered by V3).
   - Creating a batch with a non-research item still works (optional — run `iw batch-create $F_ID` from the shell; expect exit code 0).
2. Verify the dashboard has no new console errors on any page visited during V1..V4.
3. Verify the sidebar, header, and global navigation are unchanged.
4. **Screenshot:** `ai-dev/active/CR-00010/evidences/post/CR-00010_v7_no_regressions.png`.

## Pass Criteria

V1, V2, V3, V4, V5 are mandatory. V6 is optional (skip allowed with a stated reason). V(n) "no regressions" is mandatory.

Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a specific reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

## Report

After verification, write `ai-dev/active/CR-00010/reports/CR-00010_S14_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V(n).
- The exact `$IW_BROWSER_BASE_URL` used (copy from env).
- The `R_ID`, `R2_ID`, and `F_ID` seeded at the start of the run.
- Any issues found, with `file:line` references if root cause was investigated.
- A list of all screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V(n).

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00010/reports/CR-00010_S14_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00010/reports/CR-00010_S14_BrowserVerification_Report.md
```

Always include `--report` on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "CR-00010",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "seeded_ids": {"research": "R-XXXXX", "research_2": "R-XXXXX", "feature": "F-XXXXX"},
  "verifications": [
    {"id": "V1", "name": "Research detail hides approve/unapprove", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Feature detail still shows approve/unapprove", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Research absent from batch queue", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "doc-update auto-completes research item", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "iw approve on research errors", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Dashboard approve route rejects research", "status": "pass|fail|skip", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "No regressions (non-research workflow)", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every mandatory V passed (V6 may be `skip`).
- `base_url_used`: The concrete URL the agent actually hit.
- `console_errors_observed`: Any console errors seen during any V. Non-empty list on a passing run should be flagged in the report.
