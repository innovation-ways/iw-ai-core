# Browser Verification Prompt: CR-00070-S08-BrowserVerification

**Work Item**: CR-00070 -- Show Resolved Agent + Model Instead of "Inherit" in Step Runtime Dropdowns
**Step**: S08
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

Do NOT hardcode application **route paths** either (e.g. `/project/{id}/work/{item}` vs `/project/{id}/item/{item}`). Routes drift; a stale path in a verification prompt fails with a 404 that *looks* like a code defect but is a spec mismatch. Prefer to **navigate via the UI** — open a list/index page (`/history`, `/batches`, the project home) and click the link/row for the entity under test, exactly as a user would. The detail-page URL the app actually uses is whatever that link resolves to. Only fall back to a direct URL when no UI path exists, and when you do, treat any 404 as "the prompt's URL is wrong" (`spec_mismatch`), not a code defect — and report the corrected path.

Before asserting on the *content* of any page, first confirm the page itself **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors). A 500 on the page that contains the element you're verifying is itself a `code_defect` finding -- capture the server traceback (it's usually in the response body or the app container logs) and report it; do not retry the same navigation expecting a different result.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00070/CR-00070_CR_Design.md` -- the design document
- `dashboard/templates/fragments/item_steps_table.html` -- the relabelled runtime `<select>` options
- `dashboard/routers/items.py` -- `item_detail` / `item_tab_overview` render paths
- `dashboard/routers/runtime_overrides.py` -- `_render_steps_fragment` PATCH-response path
- `orch/agent_runtime/resolver.py` -- `resolve_inherited_runtime()` helper

## Output Files

- `ai-dev/active/CR-00070/reports/CR-00070_S08_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00070/evidences/post/` -- screenshots taken during verification

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
3. Screenshots go under `ai-dev/active/CR-00070/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB
via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects
current production state. It does **not** contain data that only exists in
`scripts/e2e_seed.py`'s baseline unless that script has been explicitly run.

This verification needs a work item that has **at least one editable step**
(status `pending` or `failed`) — only editable steps render the runtime
`<select>`. Production data normally contains such items. Navigate via the
project Queue / History pages to find one (an item that is queued/approved
but not yet fully executed, or one with a failed step). If no such item
exists in the seed, add an idempotent fixture file
`ai-dev/active/CR-00070/e2e_fixtures/001_item_with_pending_step.py` exporting
`def seed(db: Session) -> None` that creates a work item with one `pending`
workflow step (no step-level and no item-level runtime override), then re-run
the seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell.** The host's `.env` resolves
> to the production orchestration DB on port 5433.

If the verification can't be satisfied with seed data alone, call
`iw step-fail` with reason prefixed `ENV_DATA_MISSING:`.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> Automatically prepended by the qv-browser agent before any work-item-specific V steps. It visits every distinct page route referenced in V1..V(n), checks fragment references resolve, and reads `.playwright-cli/console-*.log` for unhandled JS/HTMX errors. If V0 fails, V1..V(n) still run.

### V1: Per-step runtime dropdown shows the resolved agent + model with "(inherited)"

1. Navigate to the project Queue or History page under `$IW_BROWSER_BASE_URL`, and click into a work item that has an editable step (status `pending` or `failed`) with no per-step and no item-level runtime override.
2. Locate the editable step's row in the steps table and read its runtime `<select>` (the CLI/Model column control). The empty option is the one that, before this CR, read `— inherit —`.
3. **Verify:** the currently-selected empty option now reads `<agent + model> (inherited)` — a concrete resolved name such as `Pi + MiniMax 2.7 (inherited)` — and **not** the bare text `— inherit —`. Confirm the model name is plainly visible (not hidden behind the word "Inherit"). Open the dropdown and confirm that same `... (inherited)` entry is the first option.
4. **Screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/CR-00070/evidences/post/CR-00070_v1_per_step_inherited.png`.

### V2: "Apply to remaining steps" dropdown shows the resolved agent + model with "(inherited)"

1. On the same item's steps table, scroll to the table footer containing the "Apply to remaining steps:" label and its `<select>`.
2. Read that bulk `<select>`'s default (empty) option.
3. **Verify:** the empty option reads `<agent + model> (inherited)` (the same resolved name as V1) instead of `— inherit —`. Open the dropdown and confirm the non-empty options are labelled with full agent + model display names (e.g. `Pi + MiniMax 2.7`), consistent with the per-step list.
4. **Screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/CR-00070/evidences/post/CR-00070_v2_apply_remaining_inherited.png`.

### V3: Relabelled option survives a runtime-override PATCH round-trip

1. On the same editable step's runtime `<select>`, select a concrete non-empty option (e.g. a specific agent + model), which fires the htmx PATCH and re-renders the steps-table fragment.
2. Wait for the fragment to settle, then on that same step's `<select>` select the empty `(inherited)` option again (clearing the override).
3. **Verify:** after each htmx swap the steps table re-renders without error, and the empty option of the step's `<select>` still reads `<agent + model> (inherited)` — confirming the PATCH-response render path (`_render_steps_fragment`) carries the relabelled option, not `— inherit —`. Confirm no console errors appeared during the PATCH round-trip.
4. **Screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/CR-00070/evidences/post/CR-00070_v3_patch_round_trip.png`.

### V4: No Regressions

1. Revisit the item detail page and the overview tab; confirm the steps table renders fully, every column (Step, Agent, CLI, Model, Status, …) is intact, and non-editable steps still show their read-only CLI/Model badges.
2. Verify no new console errors appeared on any page visited during V1..V3.
3. **Screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/CR-00070/evidences/post/CR-00070_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

### Distinguishing code defects from environment gaps and spec mismatches

Before failing the step, classify the failure using one of three classes:

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but element/data missing because seed lacks it | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + add fixture |
| Page rendered cleanly, element correctly absent per design doc, V step asks for it anyway | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` |
| Page rendered cleanly, design says element should be present, it isn't | CODE_DEFECT | normal `--reason` |

- **CODE_DEFECT** -- the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI that the design says should be present. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the page rendered cleanly with HTTP 200 but showed an empty-state message because the E2E DB lacks the rows the verification expects (here: no work item with an editable step). The fix-cycle agent **cannot** fix this by editing code; it needs an `e2e_fixtures` file. Prefix the reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 needs a work item with a pending/failed step — add ai-dev/active/CR-00070/e2e_fixtures/001_item_with_pending_step.py" \
    --report ai-dev/active/CR-00070/reports/CR-00070_S08_BrowserVerification_Report.md
  ```

- **SPEC_MISMATCH** -- the page rendered cleanly, the element is correctly absent per the design document, but the V step asks the agent to assert it is present. Prefix with `SPEC_MISMATCH:` and cite the design doc location. The fix-cycle agent MUST NOT attempt code patches for SPEC_MISMATCH findings.

### No cascading `n/a` — seed on demand

Work item authors MUST NOT write "blocked by V2 — n/a" chains. The agent is responsible for creating missing preconditions itself: use a CLI command or dashboard route the implementation provides; add/extend `ai-dev/active/CR-00070/e2e_fixtures/NNN_<name>.py` and re-run the seed inside the app container; or write the row directly via the per-worktree DB if the design supplies the SQL.

## Report

After verification, write `ai-dev/active/CR-00070/reports/CR-00070_S08_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V4.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V4.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00070/reports/CR-00070_S08_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00070/reports/CR-00070_S08_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "qv-browser",
  "work_item": "CR-00070",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Per-step dropdown shows (inherited)", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Apply-to-remaining dropdown shows (inherited)", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Relabel survives PATCH round-trip", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed or was legitimately `n/a`. `fail` on any failure.
- `overall_failure_class`: the most severe failure class observed. Severity order: `spec_mismatch` > `env_data_missing` > `code_defect`. `null` when `overall_status` is `pass`.
- `failure_class` per verification: `null` when status is `pass` or `n/a`.
- `base_url_used`: the concrete URL the agent actually hit.
- `console_errors_observed`: any console errors seen during any V(n), even on a passing run.
