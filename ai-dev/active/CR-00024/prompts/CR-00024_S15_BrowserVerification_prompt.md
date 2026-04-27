# Browser Verification Prompt: CR-00024-S15-BrowserVerification

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
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
will apply it as part of the merge pipeline. If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide.

Do NOT run any of the following:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (AC6 — primary for this step)
- `ai-dev/active/CR-00024/evidences/pre/CR-00024-running-before.png` — pre-state for visual diff
- `ai-dev/active/CR-00024/evidences/pre/CR-00024-worktrees-before.png` — pre-state for visual diff
- `dashboard/templates/fragments/running_table.html` — the modified template
- `dashboard/templates/fragments/step_row.html` — the modified template
- `dashboard/templates/fragments/jobs_table.html` — the modified template

## Output Files

- `ai-dev/active/CR-00024/reports/CR-00024_S15_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/CR-00024/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:

1. Always call `playwright-cli snapshot` BEFORE `fill` / `click` to read the current accessible element IDs.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00024/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack starts with a fresh PostgreSQL with schema + migrations applied,
plus `scripts/e2e_seed.py` (project row, architecture map, three demo work
items: F-00055, CR-00001, I-00001).

This step requires at least ONE running `StepRun` row to be visible on
`/system/running` so the heartbeat-age column has data to render. If the seed
doesn't include a running step, add a fixture:

```
ai-dev/active/CR-00024/e2e_fixtures/001_running_step.py
```

The file must export `def seed(db: Session) -> None`. Insert a `WorkItem`, a
`WorkflowStep` with `status=in_progress`, and a `StepRun` with `status=running`,
`pid=99999` (a high number guaranteed not to be alive — that's fine for the
display test), `pid_alive=True` (set by the seed for visual demo), and
`last_heartbeat = now() - INTERVAL '30 seconds'`.

Make seeding idempotent (`db.get(...)` before insert).

If a fixture would be more complex than the verification itself, instead call
`iw step-fail` with `ENV_DATA_MISSING:` (see Pass Criteria).

## Verification Steps

### V1: `/system/running` shows the new "Last seen" column with rendered age

1. Navigate to `${IW_BROWSER_BASE_URL}/system/running`.
2. **Verify:** the table contains a column header titled "Last seen" (or equivalent — verify against `running_table.html` source).
3. **Verify:** at least one row shows a value matching the pattern `Xs ago` / `Xm ago` / `Xh ago` / `unknown` in that column.
4. **Verify:** the existing columns (Step ID, Status, Started, Duration) are unchanged in label and order.
5. **Screenshot:** `ai-dev/active/CR-00024/evidences/post/CR-00024_v1_running_last_seen.png`.

### V2: `/system/running` shows the pid-alive indicator pip

1. Stay on `${IW_BROWSER_BASE_URL}/system/running`.
2. **Verify:** each row has a small coloured pip element next to its step_id or status. Use `playwright-cli snapshot` to confirm an element with class `pip` (or a `<span>` with the inline color attribute the implementation chose) is present.
3. **Verify:** the pip's `title` attribute reads "PID alive at last poll" / "PID dead at last poll" / "PID status unknown" depending on state.
4. **Screenshot:** `ai-dev/active/CR-00024/evidences/post/CR-00024_v2_running_pip.png`.

### V3: `/system/worktrees` shows the heartbeat info per active step

1. Navigate to `${IW_BROWSER_BASE_URL}/system/worktrees`.
2. **Verify:** for each worktree with an active step, the row shows the "Last seen" age AND the pid-alive pip alongside the existing git-status info.
3. **Verify:** worktrees with NO active step still render correctly (no JS error, no blank space breaking layout).
4. **Screenshot:** `ai-dev/active/CR-00024/evidences/post/CR-00024_v3_worktrees.png`.

### V4: `/system/jobs` heartbeat column appears for step-run rows only

1. Navigate to `${IW_BROWSER_BASE_URL}/system/jobs`.
2. **Verify:** rows representing step-runs show the heartbeat age; rows representing other job types (CodeIndexJob, DocGenerationJob) show `—` (em-dash) in the same column — NOT a JS error, NOT a missing cell breaking row alignment.
3. **Screenshot:** `ai-dev/active/CR-00024/evidences/post/CR-00024_v4_jobs.png`.

### V5: NULL last_heartbeat renders as "unknown" (boundary)

1. If the seed produced a row with `last_heartbeat = NULL` (e.g., a step that just launched and hasn't been polled yet), navigate to `/system/running`.
2. **Verify:** that row shows "unknown" in the Last seen column (NOT "0s ago" / blank / NaN).
3. **Screenshot:** `ai-dev/active/CR-00024/evidences/post/CR-00024_v5_null_heartbeat.png`.
4. If no NULL-heartbeat row exists in the seed, document this in the report and skip the visual assertion (the boundary is covered by the unit test in S08; the browser test is best-effort here).

### V6: No Regressions

1. Visit `${IW_BROWSER_BASE_URL}/` (project list) and one project's queue page. Verify they still render with no console errors.
2. Compare `evidences/post/CR-00024_v1_running_last_seen.png` against `evidences/pre/CR-00024-running-before.png` — confirm only the new column and pip are different; existing columns are unchanged.
3. **Verify:** no console errors appeared on any page visited during V1..V5. Use the browser dev tools panel via `playwright-cli`.
4. **Screenshot:** `ai-dev/active/CR-00024/evidences/post/CR-00024_v6_no_regressions.png` (project queue page).

## Pass Criteria

All V1..V6 must pass. Any failure — including a partial or ambiguous result —
requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly with HTTP 200 but showed an empty-state message ("No running steps") because the E2E DB lacks the rows the verification expects. Add an `e2e_fixtures` file or fail with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 expects a running StepRun row — add ai-dev/active/CR-00024/e2e_fixtures/001_running_step.py" \
    --report ai-dev/active/CR-00024/reports/CR-00024_S15_BrowserVerification_Report.md
  ```

## Report

Write `ai-dev/active/CR-00024/reports/CR-00024_S15_BrowserVerification_Report.md` containing:

- Pass/fail table with one row per V1..V6.
- The exact `$IW_BROWSER_BASE_URL` used.
- Issues found, with `file:line` references if root cause was investigated.
- List of screenshots captured.
- A **No regressions observed** subsection covering V6.

Then call ONE of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00024/reports/CR-00024_S15_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00024/reports/CR-00024_S15_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "CR-00024",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "running_last_seen", "status": "pass|fail", "screenshot": "evidences/post/CR-00024_v1_running_last_seen.png", "notes": ""},
    {"id": "V2", "name": "running_pip", "status": "pass|fail", "screenshot": "evidences/post/CR-00024_v2_running_pip.png", "notes": ""},
    {"id": "V3", "name": "worktrees_heartbeat", "status": "pass|fail", "screenshot": "evidences/post/CR-00024_v3_worktrees.png", "notes": ""},
    {"id": "V4", "name": "jobs_heartbeat_step_runs_only", "status": "pass|fail", "screenshot": "evidences/post/CR-00024_v4_jobs.png", "notes": ""},
    {"id": "V5", "name": "null_heartbeat_unknown", "status": "pass|fail|skipped", "screenshot": "evidences/post/CR-00024_v5_null_heartbeat.png", "notes": ""},
    {"id": "V6", "name": "no_regressions", "status": "pass|fail", "screenshot": "evidences/post/CR-00024_v6_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
