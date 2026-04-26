# Browser Verification Prompt: F-00063-S14-BrowserVerification

**Work Item**: F-00063 -- Stale Process & Migration Detector
**Step**: S14
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

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide.

Do NOT run any of the following:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/F-00063/F-00063_Feature_Design.md`
- `dashboard/routers/staleness.py`
- `dashboard/templates/fragments/staleness_panel.html`
- `dashboard/templates/fragments/staleness_dot.html`
- `dashboard/templates/fragments/staleness_confirm.html`
- `dashboard/templates/pages/project/dashboard.html`
- `projects.toml`
- `bin/restart-dashboard.sh`

## Output Files

- `ai-dev/active/F-00063/reports/F-00063_S14_BrowserVerification_Report.md`
- `ai-dev/active/F-00063/evidences/post/` -- screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then if the dashboard requires login (it currently does not in this project; if a login screen appears, follow the snapshot/fill/click sequence in the template):

```bash
playwright-cli snapshot
# inspect for any login form; if present:
# playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
# playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
# playwright-cli click <submit-button-ref>
```

Rules:

1. Always `playwright-cli snapshot` before `fill`/`click` to read the current accessible element IDs.
2. Wait for navigation/transitions to settle before re-snapshotting.
3. Save screenshots under `ai-dev/active/F-00063/evidences/post/`.

## E2E DB seed data

The E2E stack starts with a fresh PostgreSQL with the schema and migrations applied, plus the baseline seed in `scripts/e2e_seed.py` (project row, architecture map, three demo work items). It does NOT mirror production.

If your verifications require a project to have a stale service (which depends on real `/proc` and a real running daemon), add a fixture file under `ai-dev/active/F-00063/e2e_fixtures/` to manufacture the appearance of staleness — likely by writing a `projects.toml` entry that points `detect.type = "pgrep"` at a process you can launch in the e2e container, then advancing main with a commit touching the watched paths. Make seeding idempotent.

Alternatively, if seed data alone cannot exercise staleness (the e2e stack runs no daemon process), test the **rendering paths** with mocked staleness results via a project that has only the alembic block configured with an unreachable DB env var — the panel will render an "unreachable" migrations section deterministically.

If the verifications cannot be satisfied with seed data, call `iw step-fail` with reason prefixed `ENV_DATA_MISSING:` and add an `ai-dev/active/F-00063/e2e_fixtures/001_staleness_demo.py` file describing what is needed.

> ⚠️ **NEVER run the fixture seed from your host shell.** The host's `.env` resolves to the production orchestration DB on port 5433.

## Verification Steps

### V1: Project list shows red dot for a project with stale state

1. Navigate to `{{IW_BROWSER_BASE_URL}}/`.
2. Observe the project list. The fixture sets up `iw-ai-core` (or the dogfood project in the e2e stack) with at least one stale signal — alembic head mismatch or a stale service.
3. **Verify:** A red dot (`.iw-staleness-dot--red`) is rendered next to the affected project's name/card. A project with no staleness config (e.g. `cv`) has no dot at all.
4. **Screenshot:** `ai-dev/active/F-00063/evidences/post/F-00063_V1_project_list_red_dot.png`.

### V2: Project home renders the staleness panel with Migrations on top

1. Navigate to `{{IW_BROWSER_BASE_URL}}/projects/iw-ai-core` (or the dogfood project in the e2e stack).
2. Wait for the htmx panel fragment to load (look for the `<section>` containing the Services / Migrations sections).
3. **Verify:** A "Migrations" section is rendered ABOVE a "Services" section. If alembic is `unreachable` in the e2e stack, the migrations section shows the connection error banner; if `stale`, it shows "DB at X, code has Y".
4. **Verify:** Each service row shows a status badge (`up_to_date` / `stale` / `not_running`) with a visible text label, not colour-only.
5. **Screenshot:** `ai-dev/active/F-00063/evidences/post/F-00063_V2_project_home_panel.png`.

### V3: Confirm dialog appears before restart and shows the literal command

1. On the project home page, locate a service row that has a `Restart` button (status=stale, `restart_command` configured).
2. `playwright-cli snapshot` to find the button ref. `playwright-cli click <button-ref>`.
3. **Verify:** A modal/dialog appears titled "Confirm restart of <service_name>" containing the literal command string (e.g. `./ai-core.sh daemon restart`) inside a `<code>` block, with `Confirm` and `Cancel` buttons.
4. Click `Cancel` to close the dialog without firing the action.
5. **Screenshot:** `ai-dev/active/F-00063/evidences/post/F-00063_V3_confirm_dialog.png`.

### V4: Auto-refresh updates the panel without a manual reload

1. With the project home page open, capture a snapshot of the panel fragment's outer HTML (via `playwright-cli snapshot` — note the timestamp/start-time field that should change).
2. Wait 16 seconds (the `every 15s` timer plus jitter).
3. Re-snapshot and observe the panel has been re-rendered (any inline timestamp / "now" relative time has refreshed).
4. **Verify:** the panel section is still present and re-rendered (not a 4xx/5xx empty state).
5. **Screenshot:** `ai-dev/active/F-00063/evidences/post/F-00063_V4_auto_refresh.png`.

### V5: Opt-out project has zero staleness footprint

1. Navigate to `{{IW_BROWSER_BASE_URL}}/projects/cv` (the project with neither services nor alembic configured).
2. **Verify:** No staleness panel is visible (no Services section, no Migrations section, no red/grey dot in the page header). The rest of the project page renders normally.
3. **Screenshot:** `ai-dev/active/F-00063/evidences/post/F-00063_V5_opt_out_project.png`.

### V6: No Regressions

1. Revisit the existing flows adjacent to the changed pages: open a batch detail page, the worktrees page, the docs library — confirm they still load and behave correctly.
2. Verify no new console errors appeared on any page visited during V1–V5 (run `playwright-cli console` or read the events block reported by `playwright-cli open` / `snapshot`).
3. **Screenshot:** `ai-dev/active/F-00063/evidences/post/F-00063_V6_no_regressions.png`.

## Pass Criteria

All V1–V6 must pass. Any failure — including a partial or ambiguous result — requires `iw step-fail`. There is no "mostly passed".

### Distinguishing CODE DEFECT from ENV_DATA_MISSING

- **CODE DEFECT** — page returned HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. Use a normal `--reason`.
- **ENV_DATA_MISSING** — page rendered cleanly with HTTP 200 but the e2e stack lacks the seed data needed to manufacture a stale state. Prefix the reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 expects iw-ai-core with at least one stale signal in the e2e stack — add ai-dev/active/F-00063/e2e_fixtures/001_staleness_demo.py" \
    --report ai-dev/active/F-00063/reports/F-00063_S14_BrowserVerification_Report.md
  ```

## Report

Write `ai-dev/active/F-00063/reports/F-00063_S14_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1–V6.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if you investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00063/reports/F-00063_S14_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00063/reports/F-00063_S14_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "F-00063",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "project list red dot", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "project home panel", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "confirm dialog", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "auto-refresh", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "opt-out project", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "no regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
