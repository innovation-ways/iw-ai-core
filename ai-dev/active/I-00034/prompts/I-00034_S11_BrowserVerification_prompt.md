# Browser Verification Prompt: I-00034-S11-BrowserVerification

**Work Item**: I-00034 -- Item view step Duration is incorrect when a step goes through retries or fix cycles
**Step**: S11
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

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:9900`, no `localhost:3100`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00034/I-00034_Issue_Design.md` -- the design document
- `dashboard/routers/items.py` -- the router modified by S01
- `dashboard/templates/fragments/item_overview.html` -- renders the Duration column
- `dashboard/templates/fragments/item_header.html` -- renders the Total Time card
- `scripts/e2e_seed.py` -- baseline E2E seed (read this first to understand what's already in the DB)

## Output Files

- `ai-dev/active/I-00034/reports/I-00034_S11_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00034/evidences/post/` -- screenshots taken during verification
- `ai-dev/active/I-00034/e2e_fixtures/001_i00034_retry_history.py` -- seed fixture (see "E2E DB seed data" below; create ONLY if missing)

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

(If the dashboard has no login gate, skip the login step and document this in the report.)

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00034/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack starts with a **fresh PostgreSQL** that has the project's schema and migrations applied, plus the baseline seed in `scripts/e2e_seed.py` (project row, architecture map, three demo work items: F-00055, CR-00001, I-00001). It does **not** mirror the production database, and it does **not** contain items with multi-run `step_runs` or `fix_cycles` rows.

**This verification REQUIRES seeded fix-cycle history**, so you MUST add a fixture file:

```
ai-dev/active/I-00034/e2e_fixtures/001_i00034_retry_history.py
```

The file must export `def seed(db: Session) -> None` and will be auto-run by `scripts/e2e_seed.py` after the central seed. Make seeding idempotent (check `db.get(...)` before insert) — `e2e_up.sh` may re-run on retry.

**Required seed content** (adjust ORM imports to match `orch/db/models.py`):

1. A `WorkItem` (use ID `I-00034-RETRY-DEMO`, type `incident`, status `completed`) on the default E2E project.
2. ONE `WorkflowStep` for that item (step_id `S01`, agent backend-impl, status `completed`). Set `step.started_at = datetime(2026, 4, 22, 12, 10, 0, UTC)` and `step.completed_at = datetime(2026, 4, 22, 12, 10, 30, UTC)` — this simulates the daemon's post-retry state where the per-step timestamps reflect only the last iteration.
3. TWO `StepRun` rows linked to that step:
   - `run_number=1`, status `failed`, `started_at=2026-04-22 12:00:00Z`, `completed_at=2026-04-22 12:02:00Z`
   - `run_number=2`, status `completed`, `started_at=2026-04-22 12:10:00Z`, `completed_at=2026-04-22 12:10:30Z`
4. ONE `FixCycle` row linked to that step: `cycle_number=1`, status `completed`, `started_at=2026-04-22 12:03:00Z`, `completed_at=2026-04-22 12:09:00Z`.
5. A second `WorkItem` (ID `I-00034-HAPPY-DEMO`, type `incident`, status `completed`) with ONE `WorkflowStep` that ran exactly once: `step.started_at=T0`, `completed_at=T0+45s`, one matching `StepRun` only. No `FixCycle`. This is the happy-path control for V2.

The fixture is made visible to the E2E dashboard container via the bind-mount declared in `docker-compose.e2e.yml` (`./ai-dev:/app/ai-dev:ro`), so a file you write into this worktree will be picked up by `scripts/e2e_seed.py` when the container (re-)starts — there is nothing you need to "fall back" to.

**NEVER run the seed fixture from your host shell.** The host's `.env` points at the production orchestration DB on port 5433, NOT at the isolated E2E Postgres. A command like `uv run python -c "from orch.db.session import get_session; ..."` executed outside a container will poison the live DB and leave the E2E stack unchanged (see the 2026-04-22 I-00034 incident). If the fixture needs to be re-seeded against an already-running stack, use `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard uv run python scripts/e2e_seed.py` — that runs inside the container where `IW_CORE_DB_HOST=e2e-db`. If the stack is wedged, `iw step-fail` with `ENV_DATA_MISSING:` so the orchestrator re-provisions.

## Verification Steps

### V1: Retry-prone step shows aggregated Duration (the core fix)

1. Navigate to `$IW_BROWSER_BASE_URL/project/<default-e2e-project>/item/I-00034-RETRY-DEMO`. (The default E2E project ID is the one used by the baseline seed — read `scripts/e2e_seed.py` to determine it.)
2. Wait for the page to settle. Locate the step table row for `S01`.
3. **Verify:** The **Duration** cell for `S01` reads `10m30s` (or equivalently `10m 30s` / `630s` depending on the project's formatter). It must NOT read `30s`, `0m30s`, or anything ≤ 1 minute. The exact expected format follows `dashboard/templates/fragments/item_overview.html` — currently `"%dm%02ds" % (m, s)` → `"10m30s"`.
4. **Verify:** The **Started** column for `S01` reads `12:00:00` (localised — adjust for the timezone the dashboard displays; if the dashboard renders UTC, it's `12:00:00`, if it localises, compute the correct local-time equivalent of `2026-04-22 12:00:00Z`). It must NOT read `12:10:00` — that would indicate the aggregated earliest-start was not surfaced.
5. **Verify:** The **Total Time** metric card at the top of the Item header includes at least `10m30s` (it may be longer if synthetic setup/merge steps contribute additional span).
6. **Screenshot:** `ai-dev/active/I-00034/evidences/post/I-00034_v1_retry_demo_duration.png`.

### V2: Happy-path step unchanged (no regression)

1. Navigate to `$IW_BROWSER_BASE_URL/project/<default-e2e-project>/item/I-00034-HAPPY-DEMO`.
2. Wait for the page to settle. Locate the step table row for `S01`.
3. **Verify:** The **Duration** cell reads `0m45s` (exact). It must not have shifted from the pre-fix value — this is the regression check.
4. **Verify:** Total Time metric card reads ≥ `0m45s` and ≤ `2m` (allowing for synthetic step spans).
5. **Screenshot:** `ai-dev/active/I-00034/evidences/post/I-00034_v2_happy_path_unchanged.png`.

### V3: No Regressions (adjacent flows + console)

1. Navigate to the project dashboard home `$IW_BROWSER_BASE_URL/project/<default-e2e-project>` and verify it renders.
2. Navigate to the running items view `$IW_BROWSER_BASE_URL/running` (or the equivalent path per `dashboard/routers/running.py`) and verify it renders.
3. Navigate to the batches view if reachable (`.../batches`) and verify it renders — the batches view computes its own duration from `BatchItem`, should be unaffected.
4. Verify no new console errors appeared on any page visited during V1..V2. (Use `playwright-cli` to collect console logs and include the count in the report — zero errors expected.)
5. **Screenshot:** `ai-dev/active/I-00034/evidences/post/I-00034_v3_no_regressions.png`.

## Pass Criteria

All V1..V3 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** -- the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed `30s` instead of `10m30s`. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the page rendered cleanly with HTTP 200 but showed an empty-state message ("Work item not found", "No steps") because the seed fixture didn't actually insert the demo items. The fix-cycle agent **cannot** fix this by editing `dashboard/routers/items.py`; it needs the `e2e_fixtures` seed file to be created / corrected. Prefix the reason with `ENV_DATA_MISSING:` so the daemon recognises the class:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 expects I-00034-RETRY-DEMO with 2 step_runs + 1 fix_cycle — add ai-dev/active/I-00034/e2e_fixtures/001_i00034_retry_history.py" \
    --report ai-dev/active/I-00034/reports/I-00034_S11_BrowserVerification_Report.md
  ```

  The reason is for the human reviewer; the fix path is to add/correct the fixture, not to retry.

## Report

After verification, write `ai-dev/active/I-00034/reports/I-00034_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V4.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- The exact Duration/Started/Total-Time values observed in V1 and V2 (as rendered by the dashboard).
- Any issues found, with `file:line` references if you investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V4.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00034/reports/I-00034_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00034/reports/I-00034_S11_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00034",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Retry-prone step aggregated duration", "status": "pass|fail", "screenshot": "ai-dev/active/I-00034/evidences/post/I-00034_v1_retry_demo_duration.png", "notes": "Duration observed: ..."},
    {"id": "V2", "name": "Happy-path unchanged", "status": "pass|fail", "screenshot": "ai-dev/active/I-00034/evidences/post/I-00034_v2_happy_path_unchanged.png", "notes": ""},
    {"id": "V3", "name": "No regressions", "status": "pass|fail", "screenshot": "ai-dev/active/I-00034/evidences/post/I-00034_v3_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed. `fail` on any failure.
- `base_url_used`: The concrete URL the agent actually hit -- used by reviewers to confirm the worktree stack (not the dev server) was tested.
- `console_errors_observed`: Any console errors seen during any V(n), even if the verification otherwise passed. A non-empty list on a passing run should be flagged in the report.
