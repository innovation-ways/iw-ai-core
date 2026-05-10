# Browser Verification Prompt: I-00075-S13-BrowserVerification

**Work Item**: I-00075 -- Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills
**Step**: S13
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
  4. `docker compose -p "$COMPOSE_PROJECT_NAME" exec app …` to re-run the seed
     after writing a fixture file (this is the documented mechanism — see
     "E2E DB seed data" below). Other docker compose subcommands are NOT
     allowed.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run any alembic command. The qv-browser step does not generate
migrations. If your verification appears to require a schema change, that is
a SPEC_MISMATCH and you MUST raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:3100`). Always use the env var.

Do NOT run any of the following — they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/restart/build` command — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00075/I-00075_Issue_Design.md` -- the design document (read § Browser Verification Test, § Acceptance Criteria, § Notes)
- `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` -- the fixture this verification depends on
- `dashboard/templates/components/step_pipeline.html` -- lines 33–41 are the render branch under test (do NOT modify; read only)
- `dashboard/routers/items.py` -- lines 367–374 and 483 (where `fix_cycle_count` is computed)

## Output Files

- `ai-dev/active/I-00075/reports/I-00075_S13_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00075/evidences/post/` -- screenshots taken during verification

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

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00075/evidences/post/`.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`).

After the pg_dump restore, the daemon also runs `scripts/e2e_apply_item_fixtures.py I-00075` inside the `app` container, which discovers `ai-dev/active/I-00075/e2e_fixtures/*.py` and calls each `seed(db)` function in lexical order. **At the moment this verification runs, the daemon has already applied `001_fix_cycle_demo.py`.** You should NOT need to re-run the seed yourself.

If for any reason `I-99001` is missing from the History page (the fixture did not load), check first whether the fixture file is present in the worktree:

```bash
ls -l ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py
```

If the file is present but the data is missing, the daemon's fixture apply hook may have failed silently. Re-run the seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_apply_item_fixtures.py I-00075
```

> ⚠️ **NEVER run the seed from your host shell.** The host's `.env` resolves
> to the production orchestration DB on port 5433 — running the seed outside
> a container would write demo rows into the real DB.

If `docker compose exec` fails (container unreachable), classify as
ENV_DATA_MISSING and call `iw step-fail` with a `ENV_DATA_MISSING:` prefix —
do NOT classify as code defect.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> Automatically prepended by the qv-browser agent. Documented here for transparency.

The agent will visit every distinct page route referenced in V1..V3 and:

- Extract all fragment references (`hx-target="#X"`, `hx-include="#X"`, `aria-controls="X"`, `aria-labelledby="X"`, `href="#X"`, `for="X"`) from the rendered HTML via `curl`.
- Verify each referenced `id="X"` is present in the same HTML response.
- Read `.playwright-cli/console-*.log` after each page load to detect unhandled JS or HTMX errors.
- Flag any dangling reference or unhandled load-time error as a V0 FAIL.

If V0 fails, V1..V3 still run.

### V1: Fix-cycle amber `↺S02` pills render on the synthetic I-99001 item

1. Navigate to `${IW_BROWSER_BASE_URL}/project/iw-ai-core/item/I-99001`. The fixture (`ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py`) seeded this item with 3 WorkflowSteps and **exactly 2** FixCycle rows attached to S02.
2. Wait for the page to render. The Step Pipeline section lives near the top of the item-detail page and is rendered by the `step_pipeline` macro in `dashboard/templates/components/step_pipeline.html`.
3. **Verify** (snapshot the pipeline element, then assert against the rendered HTML — use `curl` if needed for exact attribute matching):
   - At least one `<div class="iw-pipeline-pill iw-pipeline-pill--fixcycle">` element exists in the rendered HTML.
   - Exactly **2** elements with class `iw-pipeline-pill--fixcycle` are present (matching the design's deliberate 2-cycle count).
   - The two `iw-pipeline-pill--fixcycle` divs each carry a `title="↺S02: fix cycle 1"` and `title="↺S02: fix cycle 2"` respectively (per `step_pipeline.html:37`).
   - Each amber pill is preceded by a `<div class="iw-pipeline-connector iw-pipeline-connector--fixcycle"></div>` element (per `step_pipeline.html:35`).
   - The pill's inner `<span class="iw-pipeline-pill-id">↺S02</span>` is visually present (the `↺` character, U+21BA, appears in the accessibility snapshot).
4. **Screenshot:** `playwright-cli screenshot` (no path argument), then `cp .playwright-cli/page-*.png ai-dev/active/I-00075/evidences/post/I-00075_v1_fix_cycle_amber_pills.png`.

### V2: No regression — non-fixture item with zero fix cycles still renders cleanly

1. Navigate to `${IW_BROWSER_BASE_URL}/project/iw-ai-core/item/CR-00001` (or any item visible in the History page that came from the production pg_dump and has `Fix Cycles = 0`).
2. Wait for the page to render.
3. **Verify**:
   - The Step Pipeline section renders without errors.
   - **Zero** elements with class `iw-pipeline-pill--fixcycle` are present in the rendered HTML for this item.
   - **Zero** elements with class `iw-pipeline-connector--fixcycle` are present.
   - No new console errors appear in `.playwright-cli/console-*.log` for this page load.
4. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00075/evidences/post/I-00075_v2_no_regression_zero_cycle_item.png`.

### V3: No regressions — adjacent item-overview flows

1. Visit at least one batch detail page (e.g. `${IW_BROWSER_BASE_URL}/project/iw-ai-core/batches`) and confirm the batch list renders.
2. Visit the History page (`${IW_BROWSER_BASE_URL}/project/iw-ai-core/history`) and confirm the demo item `I-99001` appears alongside the production-pg_dump items.
3. Verify no new console errors appeared on any page visited during V1..V2.
4. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00075/evidences/post/I-00075_v3_no_regressions.png`.

## Pass Criteria

All of V1, V2, V3 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps and spec mismatches

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but `iw-pipeline-pill--fixcycle` missing because fixture didn't load | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + investigate fixture apply hook |
| Page rendered cleanly, design says element should be present, it isn't | CODE_DEFECT | normal `--reason` |
| V step asserts something the design does not actually require | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` |

If `I-99001` is missing entirely from the History page, classify as ENV_DATA_MISSING (the fixture did not load) and include the path of the missing fixture in the reason. The fix-cycle agent CANNOT patch this — it needs the fixture file.

If `I-99001` is present but renders ZERO `iw-pipeline-pill--fixcycle` elements, that is a CODE_DEFECT — either the fixture seeded the wrong rows or the render branch in `step_pipeline.html:33-41` regressed.

### No cascading `n/a`

Do not write "blocked by V1 — n/a" chains. The fixture is in scope and the daemon's fixture-apply hook MUST have loaded it. If it didn't, that is the bug — report it and stop, do not skip downstream Vs.

## Report

After verification, write `ai-dev/active/I-00075/reports/I-00075_S13_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V0..V3.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env).
- Any issues found, with `file:line` references if root cause was investigated.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V2 and V3.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00075/reports/I-00075_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00075/reports/I-00075_S13_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00075",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Fix-cycle amber pills render on I-99001", "status": "pass|fail", "failure_class": "code_defect|env_data_missing|null", "screenshot": "I-00075_v1_fix_cycle_amber_pills.png", "notes": ""},
    {"id": "V2", "name": "No regression on zero-cycle item", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "I-00075_v2_no_regression_zero_cycle_item.png", "notes": ""},
    {"id": "V3", "name": "No regressions on adjacent flows", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "I-00075_v3_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "I-00075_v1_fix_cycle_amber_pills.png",
    "I-00075_v2_no_regression_zero_cycle_item.png",
    "I-00075_v3_no_regressions.png"
  ],
  "notes": ""
}
```
