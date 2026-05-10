# Browser Verification Prompt: I-00076-S13-BrowserVerification

**Work Item**: I-00076 -- Per-step CLI/runtime override `<select>` silently clears the override instead of setting it
**Step**: S13
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker
container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived infrastructure containers
are outside your scope. Touching them can cause multi-hour outages and data loss (see the
2026-04-22 incident in docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.
  4. `docker compose -p "$COMPOSE_PROJECT_NAME" exec app …` — used here to re-run the seed
     after writing a fixture file, and to run a read-only ORM query confirming DB state.
     Other `docker compose` subcommands are NOT allowed.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run any alembic command. The qv-browser step does not generate migrations.
If your verification appears to require a schema change, that is a SPEC_MISMATCH — raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source.
The environment is ready before this prompt runs — do NOT start, stop, or rebuild any services.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, …). Always use `$IW_BROWSER_BASE_URL`.

Do NOT run `make dev`, `make e2e-up`, any `docker compose up/down/restart/build`, `playwright install`,
`agent-browser`, or `chromium.launch()`. Use `playwright-cli` exclusively. The stack is already up.

## Input Files

- `ai-dev/active/I-00076/I-00076_Issue_Design.md` -- the design document (read § Browser Verification Script, § Acceptance Criteria, § Notes)
- `dashboard/templates/fragments/item_overview.html` -- the file the fix changed (read-only; lines for the editable-step CLI `<select>`)
- `dashboard/routers/runtime_overrides.py` -- the PATCH endpoint exercised by the `<select>` (read-only)
- `orch/agent_runtime/resolver.py` -- the cascade resolver (read-only)

## Output Files

- `ai-dev/active/I-00076/reports/I-00076_S13_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00076/evidences/post/` -- screenshots taken during verification
- (Only if needed) `ai-dev/active/I-00076/e2e_fixtures/001_editable_step_item.py` -- a fixture seeding a synthetic item with one `failed` step, if the seed DB has no item with a `pending`/`failed` step

## Prerequisites

Every run MUST start with, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules: always `playwright-cli snapshot` before `fill`/`click` to get fresh element refs; wait for
transitions to settle; screenshots go under `ai-dev/active/I-00076/evidences/post/`.

## E2E DB seed data — finding (or seeding) a step you can edit

The runtime-override `<select>` only renders for steps in `pending` or `failed` status. The E2E DB
is a `pg_dump` of the production orchestration DB and the `agent_runtime_options` catalogue (rows
1–5) is included in that dump (it was seeded by migration `ff23f562353b`).

To get a target step:

1. Open `${IW_BROWSER_BASE_URL}/project/iw-ai-core/queue` and/or `.../history`. Look for any work
   item whose Overview tab shows a step in `failed` or `pending` status (a `<select>` in the CLI
   column, not a read-only badge). Production almost always has at least one. Note the item id and
   step id.
2. If — and only if — **no** such item exists in the seed, write
   `ai-dev/active/I-00076/e2e_fixtures/001_editable_step_item.py` exporting `def seed(db): ...` that
   idempotently creates a synthetic item `I-99003` with one `WorkflowStep` (`step_id="S01"`,
   `status=StepStatus.failed`) and a minimal `Batch`/`BatchItem` so it shows in the UI (mirror the
   shape of `ai-dev/archive/F-00055/e2e_fixtures/001_f00055_workflow.py`; do NOT call `db.commit()`).
   Then re-run the seed inside the app container (the worktree is mounted at `/workspace`):
   ```bash
   docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_apply_item_fixtures.py I-00076 \
     || docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
   ```
   Never run the seed from the host shell — the host `.env` points at the production DB on port 5433.
   If `docker compose exec` is unreachable, `iw step-fail` with reason prefixed `ENV_DATA_MISSING:`.

Pick **one** target step for the verifications below. Choose an `AgentRuntimeOption` to apply that is
NOT the project default `id=1` and is `enabled` — e.g. **id 5** (`cli_tool="claude"`,
`model="claude-opus-4-7"`, label "Claude Code + Opus 4.7"). Confirm it's enabled via
`${IW_BROWSER_BASE_URL}/project/iw-ai-core/api/runtime-options` if unsure.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove)

> Automatically prepended by the qv-browser agent. Documented here for transparency. The agent visits
> every distinct page route referenced in V1..V4, extracts fragment references
> (`hx-target="#X"`, `hx-include="#X"`, `aria-controls="X"`, `aria-labelledby="X"`, `href="#X"`,
> `for="X"`) from the rendered HTML via `curl`, verifies each referenced `id="X"` exists in the same
> response, and reads `.playwright-cli/console-*.log` after each load for unhandled JS/HTMX errors.
> Dangling references or load-time errors are a V0 FAIL. If V0 fails, V1..V4 still run.

### V1: The editable-step CLI `<select>` renders the corrected markup

1. With `curl` (or `playwright-cli eval`), fetch the Overview-tab fragment for your target item:
   `${IW_BROWSER_BASE_URL}/project/iw-ai-core/item/<ITEM_ID>/tab/overview`.
2. **Verify** the rendered HTML for the target step's CLI `<select>` (the one whose `hx-patch` ends in
   `/step/<STEP_ID>/runtime-override`):
   - It carries `hx-disabled-elt="this"`.
   - It does **NOT** carry `onchange="...this.disabled..."` — i.e. the substring `this.disabled` does
     not appear, and `htmx.trigger(this` does not appear, anywhere in the fragment.
   - It still carries `name="option_id"` and `hx-patch=".../step/<STEP_ID>/runtime-override"`.
3. **Screenshot:** `playwright-cli screenshot` (no path arg), then
   `cp .playwright-cli/page-*.png ai-dev/active/I-00076/evidences/post/I-00076_v1_select_markup.png`.

### V2: Selecting an option fires exactly one successful PATCH (no double-fire, no error)

1. Navigate (in the browser) to `${IW_BROWSER_BASE_URL}/project/iw-ai-core/item/<ITEM_ID>` and the
   Overview tab. `playwright-cli snapshot` to locate the target step row's CLI combobox ref.
2. `playwright-cli select <combobox-ref> "Claude Code + Opus 4.7"` — picking a non-default option is
   exactly the operator action that was broken.
3. Wait for the request to settle. **Verify:**
   - `.playwright-cli/console-*.log` shows no JS/HTMX errors for this interaction.
   - The PATCH to `…/step/<STEP_ID>/runtime-override` returned `204` (inspect the network/console log;
     if the CLI surfaces request logs, confirm a single `PATCH …/runtime-override 204` — the old code
     fired this twice with an empty body).
4. **Screenshot:**
   `cp .playwright-cli/page-*.png ai-dev/active/I-00076/evidences/post/I-00076_v2_select_applied.png`.

### V3: The override was actually persisted (DB confirmation)

1. Run a read-only ORM query inside the app container (the worktree DB is what the dashboard wrote to):
   ```bash
   docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python - <<'PY'
   from orch.db.session import SessionLocal
   from orch.db.models import WorkflowStep, DaemonEvent
   import os
   item = os.environ.get("IW_ITEM_ID")  # NOTE: use the *target* item id you chose, not necessarily $IW_ITEM_ID
   PY
   ```
   (Adjust the script to look up your chosen `<ITEM_ID>`/`<STEP_ID>`.)
2. **Verify:**
   - `workflow_steps.agent_runtime_option_id` for the target step equals **5** (the option you picked) —
     i.e. the override was *set*, not cleared to NULL.
   - Exactly **one** new `daemon_events` row with `event_type = 'runtime_override_changed'` for that
     item carries `metadata->>'new_option_id' = '5'` (not `null`, and not two rows).
3. **Screenshot:** capture the dashboard's item **Logs / Events** view showing the
   `runtime_override_changed` entry, then
   `cp .playwright-cli/page-*.png ai-dev/active/I-00076/evidences/post/I-00076_v3_override_persisted.png`.

> If `docker compose exec` is unreachable, classify as `ENV_DATA_MISSING` and `iw step-fail` with that
> prefix. If the query shows `agent_runtime_option_id` is still `NULL` or two `new_option_id: null`
> events landed, that is a `CODE_DEFECT` — the fix did not take.

### V4: No regressions — adjacent overview-tab flows

1. On the same item's Overview tab, verify the step pipeline strip renders, the step rows render their
   CLI/Model columns (read-only badges for non-editable steps, `<select>` for editable ones), and the
   restart (`↻`) / skip (`⏭`) buttons and the "Apply to remaining steps" control are present and not
   throwing.
2. Visit `${IW_BROWSER_BASE_URL}/project/iw-ai-core/batches` and `.../history` — confirm they render.
3. **Verify** no new console errors appeared on any page visited during V1..V4.
4. **Screenshot:**
   `cp .playwright-cli/page-*.png ai-dev/active/I-00076/evidences/post/I-00076_v4_no_regressions.png`.

## Pass Criteria

All of V1..V4 must pass. Any failure — including a partial or ambiguous result — requires `iw step-fail`
with a reason. Classify each failure:

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw a console exception; PATCH returned non-204; `agent_runtime_option_id` still NULL after V2 | CODE_DEFECT | normal `--reason` |
| No item with a `pending`/`failed` step in the seed and the fixture path / `docker compose exec` is unreachable | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` |
| A V step asserts something the design does not require | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} ..."` |

No cascading `n/a`: if the seed lacks an editable step, *add the fixture* (method above) — don't write "blocked — n/a".

## Report

Write `ai-dev/active/I-00076/reports/I-00076_S13_BrowserVerification_Report.md` containing:
- A pass/fail table, one row per V0..V4.
- The exact `$IW_BROWSER_BASE_URL` used.
- The target item id / step id and the option id applied.
- Any issues found, with `file:line` if root cause was investigated.
- The list of screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V4.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00076/reports/I-00076_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00076/reports/I-00076_S13_BrowserVerification_Report.md
```

Always include `--report` on both paths.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00076",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Editable-step <select> renders corrected markup", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "I-00076_v1_select_markup.png", "notes": ""},
    {"id": "V2", "name": "Selecting an option fires one successful PATCH", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "I-00076_v2_select_applied.png", "notes": ""},
    {"id": "V3", "name": "Override persisted (agent_runtime_option_id set, single event)", "status": "pass|fail", "failure_class": "code_defect|env_data_missing|null", "screenshot": "I-00076_v3_override_persisted.png", "notes": ""},
    {"id": "V4", "name": "No regressions on adjacent overview flows", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "I-00076_v4_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "I-00076_v1_select_markup.png",
    "I-00076_v2_select_applied.png",
    "I-00076_v3_override_persisted.png",
    "I-00076_v4_no_regressions.png"
  ],
  "notes": ""
}
```
