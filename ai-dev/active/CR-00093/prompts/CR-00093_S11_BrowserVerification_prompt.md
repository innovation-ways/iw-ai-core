# Browser Verification Prompt: CR-00093-S11-BrowserVerification

**Work Item**: CR-00093 -- Register all test-enhancement Makefile suites as launchable dashboard cards
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change Docker container/volume/network state. Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed. `docker compose exec app …` is allowed for re-running fixture seeds inside the already-running E2E stack. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run any `alembic upgrade / downgrade / stamp` against the live orch DB. Read-only `alembic history / current / show` is allowed. The E2E stack's per-worktree DB is provisioned by the daemon before this prompt runs. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source. The environment is ready — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports, URLs, or credentials. Always read the env vars. Do NOT hardcode application route paths — navigate via the UI where possible (click project → click Tests / Quality tab). The dashboard mounts each project's Tests page under `/project/<project_id>/tests` and Quality page under `/project/<project_id>/quality`; resolve `<project_id>` via the project nav.

Do NOT run any of the following:
- `make dev`, `make test-e2e`, `make e2e-up`, `docker compose up/down/restart/build` — the stack is already up.
- `playwright install` or `npx playwright install` — the CLI is pre-installed.
- `agent-browser` or direct `chromium.launch()` — this environment uses `playwright-cli` **exclusively**.

## Input Files

- `ai-dev/active/CR-00093/CR-00093_CR_Design.md` — the design document.
- `.iw-orch.json` — the file modified by S01. The E2E stack's daemon reads this on launch — the new categories should already be in the per-worktree DB's `project.config`.
- `ai-dev/work/CR-00093/reports/CR-00093_S01_Backend_report.md` — the S01 report (cross-reference its category counts).

## Output Files

- `ai-dev/active/CR-00093/reports/CR-00093_S11_BrowserVerification_Report.md` — the mandatory report.
- `ai-dev/active/CR-00093/evidences/post/` — screenshots taken during verification.

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:
1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read current accessible refs.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00093/evidences/post/` with descriptive filenames. Use `playwright-cli screenshot` (no path arg), then `cp .playwright-cli/page-*.png ai-dev/active/CR-00093/evidences/post/<name>.png`.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from production. The `iw-ai-core` `Project` row exists; its `config['test_config']` and `config['quality_config']` should reflect the edited `.iw-orch.json` (the daemon synced it on stack launch). No fixture file needed — this CR doesn't depend on historical rows.

If `project.config['test_config']['categories']` still shows the pre-CR 3-entry set (smoke / properties / e2e / etc. cards missing from the page), STOP and call `iw step-fail` with `ENV_DATA_MISSING: stack did not re-read .iw-orch.json — fixture/sync issue, not a code defect`.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

(Auto-prepended — visits every route in V1..V(n), checks for dangling `hx-target` references and JS / HTMX console errors.)

### V1: Tests page shows the 21 new test cards

1. Navigate to the dashboard home, click the `iw-ai-core` project tile.
2. From the project nav, click "Tests" — lands on the Tests page at `<base-url>/project/iw-ai-core/tests`.
3. Snapshot the page. Verify:
   - The page header reads "Tests" (or similar).
   - The Launch tab is active (or click it explicitly).
   - At least **24 distinct launchable cards** are visible on the page (3 existing + 21 new). Count `<button>`s with the launch-action class OR card containers — whichever element is the per-category card.
   - Cards are grouped under headings matching the design's groups: `backend`, `suites`, `e2e`, `perf`, `chaos`, `visual`, `quality` (or close — the rendering may sort alphabetically or by registration order).
   - Specific spot-check card labels visible (snapshot regex): `Smoke`, `Property Tests`, `E2E Browser Smoke`, `Performance Budgets`, `Daemon Chaos Smoke`, `Visual Regression`, `iw CLI Contract`, `Security Test Module`.
4. **Screenshot:** `ai-dev/active/CR-00093/evidences/post/CR-00093_v1_tests_page_24_cards.png`.

### V2: Quality page shows the 9 new quality cards

1. From the project nav, click "Quality" — lands on `<base-url>/project/iw-ai-core/quality`.
2. Snapshot the page. Verify:
   - The Launch tab is active.
   - At least **13 distinct launchable cards** are visible (4 existing + 9 new).
   - Cards grouped under: `style`, `suites`, `docs`, `security`, `coverage`, `hygiene`.
   - Specific spot-check labels: `DB Column Doc Scanner`, `Secret Scan`, `SAST`, `Diff Coverage`, `Mutation Check`, `Dead Code`, `Dependency Hygiene`.
3. **Screenshot:** `ai-dev/active/CR-00093/evidences/post/CR-00093_v2_quality_page_13_cards.png`.

### V3: Launch a new test card and confirm a TestRun row appears

1. From the Tests page, click the launch button on the `Smoke` card.
2. Verify:
   - The response is a 2xx (no toast saying "category not found" or "command not found").
   - A toast appears confirming the run was launched (text like `Test run #N launched (Smoke ...)`).
3. Click the Runs tab on the same page.
4. Verify:
   - A new row is present at the top of the Runs table with category `smoke` and status `pending` or `running`.
   - The Runs row links to a live-log fragment.
5. **Screenshot:** `ai-dev/active/CR-00093/evidences/post/CR-00093_v3_smoke_run_row.png`.

DO NOT wait for the `smoke` run to complete — the qv-browser budget is for render + click verification, not end-to-end suite execution. The test_runner.py background thread + the existing test-run-launch path are already covered by CR-00072's route sweep and the existing dashboard integration tests.

### V4: Launch a new quality card and confirm a quality-run row appears

1. From the Quality page, click the launch button on the `DB Column Doc Scanner` card.
2. Verify 2xx + toast + a new Runs row with category `check-column-docs` and `run_type='quality'`.
3. **Screenshot:** `ai-dev/active/CR-00093/evidences/post/CR-00093_v4_column_docs_run_row.png`.

### V5: e2e_stack mutual exclusion (light-touch)

1. From the Tests page, click the launch button on `E2E Browser Smoke`.
2. Verify a TestRun row appears with category `e2e-smoke`.
3. WHILE the e2e-smoke run is still pending/running (if the worktree's E2E stack supports a sub-stack — if not, this verification falls back to **n/a — implementation note**: when there's no nested E2E stack capable of running a second isolated stack, the mutual-exclusion check cannot be exercised meaningfully from inside the qv-browser's own stack; skip), click the launch button on `E2E Browser Full`.
4. If exercised: verify the response is a warning toast like "E2E stack already in use by run #N (e2e-smoke) — wait for it to finish ..." and NO new `e2e` TestRun row is created.
5. **Screenshot:** `ai-dev/active/CR-00093/evidences/post/CR-00093_v5_e2e_stack_warning.png` (or document n/a in the report).

Mark this V5 as **n/a — environment limitation** (not a code defect) if the qv-browser's own stack precludes launching a sibling E2E stack; explain in the report's notes.

### V6: No Regressions

1. Revisit the Tests page; click the existing `unit` card; verify the existing launch path still works (a new `unit` TestRun row appears). Then click the existing `lint` card on the Quality page; verify a new `lint` quality-run row appears.
2. Visit the History tab on the Tests page; verify prior `unit` / `integration` TestRun rows are still listed (existing data intact).
3. Confirm no new console errors appeared on any page visited during V1..V5.
4. **Screenshot:** `ai-dev/active/CR-00093/evidences/post/CR-00093_v6_no_regressions.png`.

## Pass Criteria

All V1..V4 + V6 must pass. V5 may be `n/a — environment limitation` (documented in report). Any other failure requires `iw step-fail`. Classify per the standard taxonomy:

- **CODE_DEFECT** — page 5xx, missing card after S01 confirmed it added, console exception, launch returns non-2xx.
- **ENV_DATA_MISSING** — `project.config` in the E2E DB doesn't reflect S01's edits (stack didn't re-read .iw-orch.json — orchestrator issue, not the CR's fault). Use `ENV_DATA_MISSING:` prefix.
- **SPEC_MISMATCH** — page renders cleanly with cards matching the design, but V step asserts something the design didn't promise. Use `SPEC_MISMATCH:` prefix.

## Report

Write `ai-dev/active/CR-00093/reports/CR-00093_S11_BrowserVerification_Report.md` containing:

- Pass/fail table with one row per V0..V6.
- The exact `$IW_BROWSER_BASE_URL` used (so reviewers can confirm the worktree stack was tested, not production).
- Card counts observed: `tests_page_card_count`, `quality_page_card_count`.
- TestRun row IDs created during V3 and V4.
- Whether V5 was exercised or marked n/a (with reason).
- Screenshot inventory under `evidences/post/`.
- "No regressions observed" subsection covering V6.

Then call:

```bash
# On full pass:
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00093/reports/CR-00093_S11_BrowserVerification_Report.md

# On failure:
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00093/reports/CR-00093_S11_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "CR-00093",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<the actual $IW_BROWSER_BASE_URL>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Tests page shows ≥24 cards", "status": "pass|fail", "failure_class": null, "screenshot": "ai-dev/active/CR-00093/evidences/post/CR-00093_v1_tests_page_24_cards.png", "notes": "observed card count: <N>"},
    {"id": "V2", "name": "Quality page shows ≥13 cards", "status": "pass|fail", "failure_class": null, "screenshot": "...", "notes": "observed card count: <N>"},
    {"id": "V3", "name": "Smoke launch creates TestRun row", "status": "pass|fail", "failure_class": null, "screenshot": "...", "notes": "TestRun ID: <N>"},
    {"id": "V4", "name": "check-column-docs launch creates quality run row", "status": "pass|fail", "failure_class": null, "screenshot": "...", "notes": "TestRun ID: <N>"},
    {"id": "V5", "name": "e2e_stack mutual exclusion", "status": "pass|n/a", "failure_class": null, "screenshot": "...", "notes": "n/a reason if applicable"},
    {"id": "V6", "name": "No regressions on existing cards", "status": "pass|fail", "failure_class": null, "screenshot": "...", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": "Render-only per design — no end-to-end suite execution waited on."
}
```
