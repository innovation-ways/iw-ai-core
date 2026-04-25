# Browser Verification Prompt: I-00039-S10-BrowserVerification

**Work Item**: I-00039 -- Jobs page — drop color-coded Type chips and replace filter checkboxes with multi-select dropdowns
**Step**: S10
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

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not relevant — no DB or migration work in this incident.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from
THIS worktree's source code. The environment is ready before this prompt
runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no any
literal port). Always use the env var. The port is allocated per-worktree so
concurrent browser_verification steps don't collide; hardcoding a port is a
bug that will silently test the wrong environment.

Do NOT run any of the following — they will break the isolated stack:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00039/I-00039_Issue_Design.md` — design document
- Files modified by S01:
  - `dashboard/templates/pages/project/jobs.html`
  - `dashboard/templates/fragments/jobs_table.html`
  - `dashboard/templates/components/multi_select.html`
  - `dashboard/static/multi_select.js`
  - `dashboard/static/styles.css`
- Pre-fix evidence (compare against post-fix):
  - `ai-dev/active/I-00039/evidences/pre/I-00039-jobs-before.png`

## Output Files

- `ai-dev/active/I-00039/reports/I-00039_S10_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/I-00039/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QV Browser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

The IW AI Core dashboard does NOT have a login screen (it is local-only — see
`dashboard/CLAUDE.md`). Skip the typical login flow. If `$IW_BROWSER_E2E_USER`
is set but the dashboard's landing page does not show a login form, proceed
directly to the Jobs page.

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read
   the current accessible element IDs. Do not guess selectors or reuse refs
   from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00039/evidences/post/` with
   descriptive filenames.

## E2E DB seed data

The E2E stack starts with a fresh PostgreSQL with schema and migrations
applied, plus the baseline seed in `scripts/e2e_seed.py` (project row,
architecture map, three demo work items: F-00055, CR-00001, I-00001). It
does not mirror the production database.

For this incident, the verification needs **at least one Job row of varied
types** to render. The standard seed creates batch-execution jobs (via the
demo work items), so the Jobs page will not be empty on a clean stack. If
your verification finds the Jobs table empty, add a fixture file:

```
ai-dev/active/I-00039/e2e_fixtures/001_jobs_seed.py
```

defining `def seed(db: Session) -> None` that inserts at least one
`CodeIndexJob`, one `DocGenerationJob`, one `Batch`, and one
`research`-type `ProjectDoc`. Make it idempotent (`db.get(...)` before
insert).

If you choose this path, classify the failure as `ENV_DATA_MISSING` per
the Pass Criteria section.

## Verification Steps

The project ID for the seeded project is the same one referenced by the
demo work items — discover it from the landing page (the project list).
Replace `{project_id}` in the URLs below with the actual id observed in the
snapshot.

### V1: Type column renders as plain text (no coloured pills)

1. Navigate to `$IW_BROWSER_BASE_URL/project/{project_id}/jobs`.
2. Take an accessibility snapshot. Visually inspect the Type column in the
   first row.
3. **Verify**: the Type cell text is the same colour as the Title cell text
   (no coloured background pill). Programmatically confirm by fetching the
   raw HTML:
   ```bash
   curl -s "$IW_BROWSER_BASE_URL/project/{project_id}/jobs" \
     | grep -E 'bg-(blue|purple|orange|teal|emerald)-100'
   ```
   The grep MUST return zero matches inside any `<td>` that contains the
   `row.job_type.value` (a few may legitimately exist in unrelated places
   like status badges; investigate any match before failing).
4. **Screenshot**:
   `ai-dev/active/I-00039/evidences/post/I-00039_v1_type_plain_text.png`.

### V2: Type filter is a multi-select dropdown that filters correctly

1. On the Jobs page, locate the Type dropdown button. Click it.
2. **Verify**: a popover panel appears containing one checkbox per JobType
   (`code_mapping`, `doc_indexing`, `doc_generation`, `batch_execution`,
   `research`, `oss_scan`).
3. Check **two** boxes (e.g. `batch_execution` and `research`).
4. **Verify**: the dropdown button label updates to `Type (2 selected)`.
5. Click the **Filter** submit button.
6. **Verify**: the URL contains `?type=batch_execution&type=research` (or
   the equivalent percent-encoded form). The Jobs table now shows only
   rows of those two types — no `code_mapping`, `doc_indexing`,
   `doc_generation`, or `oss_scan` rows visible.
7. **Screenshot**:
   `ai-dev/active/I-00039/evidences/post/I-00039_v2_type_filter_active.png`.

### V3: Status filter behaves identically to Type filter

1. Click the **Clear** link to reset filters.
2. Open the Status dropdown button. Click it.
3. **Verify**: a popover panel appears with one checkbox per status
   (`queued`, `running`, `completed`, `failed`, `paused`, `cancelled`).
4. Check **one** box (e.g. `completed`).
5. **Verify**: button label updates to `Status (1 selected)`.
6. Click Filter. **Verify** URL contains `?status=completed` and the table
   shows only completed rows.
7. **Screenshot**:
   `ai-dev/active/I-00039/evidences/post/I-00039_v3_status_filter_active.png`.

### V4: Dropdown closes on outside-click and Escape

1. Click the Type dropdown button to open it. Confirm panel visible.
2. Click somewhere outside the dropdown (e.g. the page heading).
3. **Verify**: the panel is hidden.
4. Click the Type dropdown button again to reopen.
5. Press the `Escape` key.
6. **Verify**: the panel is hidden, AND focus is back on the button.
7. **Screenshot**:
   `ai-dev/active/I-00039/evidences/post/I-00039_v4_dropdown_close.png`.

### V5: No Regressions

1. Click Clear to reset filters. Verify the full Jobs table reloads.
2. Use the From / To date inputs (e.g. set From = 30 days ago, To = today).
   Click Filter. Verify the URL contains `?date_from=...&date_to=...` and
   the table re-renders without errors.
3. Click any column header to verify table sort still works (the existing
   `sortJobsTable` JS function should not have been broken).
4. Click any row's ID link — verify it navigates to the job detail page
   without console errors.
5. Open the browser devtools Console. Reload the Jobs page.
6. **Verify**: no new console errors appear (warnings about missing
   favicons or third-party SDKs that existed before are acceptable; new
   `Uncaught TypeError` / `ReferenceError` from `multi_select.js` is NOT
   acceptable).
7. **Screenshot**:
   `ai-dev/active/I-00039/evidences/post/I-00039_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure — including a partial or ambiguous
result — requires calling `iw step-fail` with a reason. There is no "mostly
passed"; if an expected element cannot be found, snapshot the page, attach
the screenshot, and fail the step.

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** — the page returned an HTTP error, threw a console
  exception, rendered the wrong element, or showed broken UI. The fix-cycle
  agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly with HTTP 200 but the
  Jobs table was completely empty (no batches, no code-index jobs, no
  research docs from the standard seed). The fix-cycle agent **cannot**
  fix this by editing code; it needs an `e2e_fixtures` file. Prefix the
  reason:
  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: Jobs table empty on default seed — add ai-dev/active/I-00039/e2e_fixtures/001_jobs_seed.py" \
    --report ai-dev/active/I-00039/reports/I-00039_S10_BrowserVerification_Report.md
  ```

## Report

After verification, write
`ai-dev/active/I-00039/reports/I-00039_S10_BrowserVerification_Report.md`
containing:

- A pass/fail table with one row per V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is
  self-contained).
- Any issues found, with `file:line` references if the agent investigated
  root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V5.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00039/reports/I-00039_S10_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00039/reports/I-00039_S10_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the
orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S10",
  "agent": "qv-browser",
  "work_item": "I-00039",
  "overall_status": "pass|fail",
  "base_url_used": "<actual $IW_BROWSER_BASE_URL value>",
  "verifications": [
    {"id": "V1", "name": "Type column plain text", "status": "pass|fail", "screenshot": "ai-dev/active/I-00039/evidences/post/I-00039_v1_type_plain_text.png", "notes": ""},
    {"id": "V2", "name": "Type multi-select filter", "status": "pass|fail", "screenshot": "ai-dev/active/I-00039/evidences/post/I-00039_v2_type_filter_active.png", "notes": ""},
    {"id": "V3", "name": "Status multi-select filter", "status": "pass|fail", "screenshot": "ai-dev/active/I-00039/evidences/post/I-00039_v3_status_filter_active.png", "notes": ""},
    {"id": "V4", "name": "Dropdown closes on outside-click and Escape", "status": "pass|fail", "screenshot": "ai-dev/active/I-00039/evidences/post/I-00039_v4_dropdown_close.png", "notes": ""},
    {"id": "V5", "name": "No regressions on adjacent flows", "status": "pass|fail", "screenshot": "ai-dev/active/I-00039/evidences/post/I-00039_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/I-00039/evidences/post/I-00039_v1_type_plain_text.png",
    "ai-dev/active/I-00039/evidences/post/I-00039_v2_type_filter_active.png",
    "ai-dev/active/I-00039/evidences/post/I-00039_v3_status_filter_active.png",
    "ai-dev/active/I-00039/evidences/post/I-00039_v4_dropdown_close.png",
    "ai-dev/active/I-00039/evidences/post/I-00039_v5_no_regressions.png"
  ],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed. `fail` on any failure.
- `base_url_used`: The concrete URL the agent actually hit — used by
  reviewers to confirm the worktree stack (not the dev server) was tested.
- `console_errors_observed`: Any console errors seen during any V(n), even
  if the verification otherwise passed. A non-empty list on a passing run
  should be flagged in the report.
