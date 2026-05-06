# Browser Verification Prompt: CR-00035-S21-BrowserVerification

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step**: S21
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

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

- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` -- the design document
- `dashboard/templates/pages/project/job_detail.html`
- `dashboard/routers/docs.py` (or `dashboard/routers/jobs_ui.py` — whichever S05 chose)
- `orch/daemon/doc_job_poller.py`
- `orch/doc_service.py`
- `orch/doc_report.py`

## Output Files

- `ai-dev/active/CR-00035/reports/CR-00035_S19_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00035/evidences/post/` -- screenshots taken during verification

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
3. Screenshots go under `ai-dev/active/CR-00035/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB
via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects
current production state. Production has at least one terminal-state
DocGenerationJob (DOC-00004 with the captured wrong-dispatch log) — that
row IS in the seed and is what V1..V3 will inspect.

> **Note:** Live-log streaming is intentionally NOT covered by this browser
> verification. The PID liveness probe runs in the daemon's PID namespace,
> not the app container's, which makes a deterministic running-job fixture
> brittle (the daemon would see the fake `sleep` PID as dead and immediately
> close the job). The S11 integration test for `/log/stream` covers that
> behaviour at a more reliable layer. See the design doc's Notes section.

## Verification Steps

### V1: Execution Report card renders for terminal jobs

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/jobs/doc_generation/DOC-00004` — the canonical failed job from production.
2. **Verify**: a card titled "Execution Report" is visible.
3. **Verify**: the card shows non-empty values for: Outcome (a status pill, expected `failed_process_exited` or similar terminal outcome), Duration, Skill, Command issued (in `<code>`), Log size, doc-update calls (expected `0`), Diagnosis (a non-empty sentence).
4. **Verify**: the Tool calls table contains at least one row with `iw item-status` (this is the wrong-dispatch fingerprint from the historical log).
5. **Verify**: the original Error card ("generation timeout after 15 minutes") still renders below the Execution Report.
6. **Screenshot:** `ai-dev/active/CR-00035/evidences/post/CR-00035_v1_execution_report_doc00004.png`.

### V2: Captured log fallback shows the historical log

1. On the same DOC-00004 page from V1, locate the `<details>` element titled "Captured log".
2. Click the `<summary>` to expand it.
3. **Verify**: the expanded `<pre>` contains text including `iw item-status 727a12bd` — the actual captured stdout from the historical run, ANSI stripped.
4. **Screenshot:** `ai-dev/active/CR-00035/evidences/post/CR-00035_v2_captured_log_expanded.png`.

### V3: Download raw log link works

1. On the same DOC-00004 page, locate the "Download raw log" link inside the Execution Report card.
2. Click it (or `playwright-cli` equivalent — fetch the href and curl it inside the container if direct download isn't trivial).
3. **Verify**: the response is `text/plain`, has `Content-Disposition: attachment`, and contains the original ANSI escapes (the `[0m` sequences from the pre-stripping log).
4. **Screenshot:** `ai-dev/active/CR-00035/evidences/post/CR-00035_v3_download_raw_log_response_headers.png` (browser dev tools network panel showing the response, OR a follow-up snapshot that proves the file downloaded).

### V4: No Regressions

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/jobs` (the unified jobs table).
2. **Verify**: the table renders without errors and DOC-00004 / DOC-00003 rows are present with the correct status pill.
3. Click into any non-doc_generation job (e.g. a code_mapping job — pick whatever exists in the seed). **Verify**: that page renders unchanged from before this CR (Parameters card present, no Live Log card, no Execution Report card — those are doc-generation only).
4. **Verify**: no NEW console errors appear on any page visited during V1..V3 (existing pre-CR console warnings are acceptable; new ones are not).
5. **Screenshot:** `ai-dev/active/CR-00035/evidences/post/CR-00035_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** -- the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the page rendered cleanly with HTTP 200 but showed an empty-state message because the E2E DB lacks the historical rows the verification expects. The fix-cycle agent **cannot** fix this by editing code; it needs an `e2e_fixtures` file. Prefix the reason with `ENV_DATA_MISSING:`.

## Report

After verification, write `ai-dev/active/CR-00035/reports/CR-00035_S21_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V4.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the unified jobs page and adjacent job-type detail pages.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00035/reports/CR-00035_S21_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00035/reports/CR-00035_S21_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S21",
  "agent": "qv-browser",
  "work_item": "CR-00035",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "Execution Report card renders for terminal jobs", "status": "pass|fail", "screenshot": "evidences/post/CR-00035_v1_execution_report_doc00004.png", "notes": ""},
    {"id": "V2", "name": "Captured log fallback shows the historical log", "status": "pass|fail", "screenshot": "evidences/post/CR-00035_v2_captured_log_expanded.png", "notes": ""},
    {"id": "V3", "name": "Download raw log link works", "status": "pass|fail", "screenshot": "evidences/post/CR-00035_v3_download_raw_log_response_headers.png", "notes": ""},
    {"id": "V4", "name": "No regressions", "status": "pass|fail", "screenshot": "evidences/post/CR-00035_v4_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
