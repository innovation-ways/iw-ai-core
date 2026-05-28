# Browser Verification Prompt: CR-00086-S16-BrowserVerification

**Work Item**: CR-00086 -- Self-dashboarding of test health
**Step**: S16
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

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.
  4. `docker compose exec app` to re-run the seed inside the app container after writing a fixture file (see "E2E DB seed data" below).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB on port 5433. The migration is already applied in the E2E stack (the per-worktree DB is restored from a pg_dump and migrations are applied during stack provisioning).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide.

Do NOT hardcode application **route paths**. Prefer to navigate via the UI — open the project page, click the Tests / Quality nav links exactly as a user would. Only fall back to a direct URL when no UI path exists, and treat any 404 as `spec_mismatch` (the prompt's URL is wrong).

Before asserting on the *content* of any page, first confirm the page itself loaded successfully (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors).

Do NOT run any of the following:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/restart/build`
- `playwright install` or `npx playwright install`
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` snippet

## Input Files

- `ai-dev/active/CR-00086/CR-00086_CR_Design.md` -- the design document
- `dashboard/templates/fragments/test_health_panel.html`
- `dashboard/routers/tests.py`
- `dashboard/routers/quality.py`
- `dashboard/templates/pages/tests.html`
- `dashboard/templates/pages/quality.html`
- `orch/test_health_service.py`
- `orch/jobs/aggregator.py`
- `orch/cli/test_health_commands.py`

## Output Files

- `ai-dev/active/CR-00086/reports/CR-00086_S16_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00086/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

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

1. Always call `playwright-cli snapshot` **before** `fill` / `click`.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00086/evidences/post/`.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump`. It does NOT contain `test_health_snapshots` rows by default because the table is new (S01 migration).

**You MUST seed snapshot data** before V1 can pass. Create a fixture file at:

```
ai-dev/active/CR-00086/e2e_fixtures/001_test_health_snapshots.py
```

The file MUST export `def seed(db: Session) -> None` and:

1. Insert at least 30 `TestHealthSnapshot` rows per metric for the `iw-ai-core` project, with timestamps spaced one hour apart and values in a plausible range:
   - `mutation_score` — values between 60.0 and 85.0 with a slight upward trend
   - `coverage_pct` — values between 70.0 and 92.0
   - `flaky_test_count` — integer values between 0 and 7
   - `assertion_baseline_size` — integer values descending from 650 to 540 (reflecting CR-00046/81 progress)
2. Insert a second project (or use an existing one) with NO snapshots, so V3's empty-state check has a target.
3. Be idempotent (`db.get(...)` / `db.scalar(select(...))` before insert).

After writing the fixture file, re-run the seed inside the `app` container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell.** The host's `.env` resolves to the production orchestration DB on port 5433.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove)

The agent prepends V0 automatically. It visits every distinct route in V1..V(n), parses fragment references, and reads `.playwright-cli/console-*.log` for unhandled JS / HTMX errors. V0 failure does NOT skip V1..V(n) — they still run.

### V1: Test Health panel renders on the Tests page with four metric cards and sparklines

1. Navigate via the UI: from the home page, click the iw-ai-core project tile, then click the "Tests" nav link.
2. Wait for the Test Health panel to load (it htmx-mounts after the page body renders) — this exercises the new `/projects/{slug}/test-health` endpoint added in S05.
3. **Verify**:
   - The panel is visible under the existing gates summary.
   - Four metric cards are present, labelled "Mutation Score", "Coverage", "Flaky Tests", "Assertion Baseline".
   - Each card shows a numeric latest value and a delta (up arrow / down arrow / dash).
   - Each card shows an inline `<svg>` with a non-empty `<path d="M ...">`.
   - No console errors fired during the load (check `.playwright-cli/console-*.log`).
4. **Screenshot**: `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/CR-00086/evidences/post/CR-00086_v1_tests_panel.png`.

### V2: Test Health panel renders on the Quality page

1. Click the "Quality" nav link (or whichever link the iw-ai-core project page exposes for the Quality view).
2. Wait for the Test Health panel to mount.
3. **Verify**: same four cards, same sparklines, same data values as V1 (the panel is the same fragment mounted on both pages).
4. **Screenshot**: `ai-dev/active/CR-00086/evidences/post/CR-00086_v2_quality_panel.png`.

### V3: Empty-state placeholder on a freshly-onboarded project (AC5)

1. Navigate to the Tests page for a project that has NO test-health snapshots (the second project seeded in the fixture, or any non-iw-ai-core managed project).
2. Wait for the Test Health panel to mount.
3. **Verify**: either four per-metric "no data yet" placeholders are visible, OR a single combined "Test health data will appear after the first capture runs" message is visible. No `<svg>` with empty path. No `NaN` text anywhere in the panel. No console errors.
4. **Screenshot**: `ai-dev/active/CR-00086/evidences/post/CR-00086_v3_empty_state.png`.

### V4: Job row appears in the unified Jobs view

1. From inside the app container (allowed per the env exception), trigger a fresh capture:
   ```bash
   docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
     uv run iw test-health-capture --project iw-ai-core
   ```
2. Navigate to the unified Jobs view (likely `/jobs` or `/system/jobs` — discover via the nav).
3. **Verify**: a row with `job_type` (or equivalent column) reading `test-health-capture` is visible at the top of the list. Its timestamp matches the capture you just triggered.
4. **Screenshot**: `ai-dev/active/CR-00086/evidences/post/CR-00086_v4_jobs_view.png`.

### V5: No Regressions

1. Revisit the gates summary on the Tests and Quality pages and confirm the existing tiles still render correctly (unit-tests count, integration-tests count, last-run timestamp).
2. Revisit one unrelated dashboard page (Queue, History, or Worktrees) and confirm it still loads cleanly.
3. Verify no new console errors appeared on any page visited during V1..V4.
4. **Screenshot**: `ai-dev/active/CR-00086/evidences/post/CR-00086_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure — including partial or ambiguous — requires `iw step-fail` with a reason.

### Failure classification

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but snapshot data missing | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + extend fixture |
| Page rendered cleanly, element correctly absent per design, V step asks for it anyway | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: ..."` |
| Page rendered cleanly, design says element should be present, it isn't | CODE_DEFECT | normal `--reason` |

### No cascading `n/a`

Do NOT write "blocked by V1 — n/a" chains. Create missing preconditions via the fixture mechanism described above.

## Report

After verification, write `ai-dev/active/CR-00086/reports/CR-00086_S16_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V0..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found with `file:line` references if you investigated root cause.
- The list of screenshots captured (relative paths under `evidences/post/`).
- A "No regressions observed" subsection covering V5.

Then call ONE of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00086/reports/CR-00086_S16_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00086/reports/CR-00086_S16_BrowserVerification_Report.md
```

Always include `--report` on both paths.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "CR-00086",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<the actual $IW_BROWSER_BASE_URL used>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Test Health panel on Tests page", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "evidences/post/CR-00086_v1_tests_panel.png", "notes": ""},
    {"id": "V2", "name": "Test Health panel on Quality page", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "evidences/post/CR-00086_v2_quality_panel.png", "notes": ""},
    {"id": "V3", "name": "Empty-state placeholder", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "evidences/post/CR-00086_v3_empty_state.png", "notes": ""},
    {"id": "V4", "name": "Capture appears in Jobs view", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "evidences/post/CR-00086_v4_jobs_view.png", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "evidences/post/CR-00086_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
