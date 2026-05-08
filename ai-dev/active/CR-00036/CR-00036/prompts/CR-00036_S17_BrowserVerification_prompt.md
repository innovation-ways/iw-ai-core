# Browser Verification Prompt: CR-00036-S17-BrowserVerification

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Step**: S17
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

Do NOT hardcode ports. Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md` -- the design document
- Files modified across S01..S10:
  - `orch/db/models.py`
  - `orch/db/migrations/versions/cr00036_*.py`
  - `orch/daemon/project_registry.py`
  - `orch/daemon/batch_manager.py`
  - `orch/cli/batch_commands.py`
  - `orch/cli/item_commands.py`
  - `dashboard/routers/items.py`
  - `dashboard/routers/actions.py`
  - `dashboard/templates/components/action_button.html`
  - `dashboard/templates/components/status_badge.html`
  - `dashboard/templates/fragments/item_overview.html`
  - `dashboard/templates/fragments/batch_detail_header.html`
  - `dashboard/templates/pages/project/batch_detail.html`
  - `dashboard/static/styles.css`

## Output Files

- `ai-dev/active/CR-00036/reports/CR-00036_S17_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00036/evidences/post/` -- screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in (if the worktree stack requires it — check by snapshotting after `open`):

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Always `snapshot` before each `fill`/`click` to read current accessible refs. Don't reuse refs across navigations.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB. If your verifications require data not yet in production (e.g., a batch with `auto_merge=false`, or an item already in the new `awaiting_merge_approval` state), add a fixture file:

```
ai-dev/active/CR-00036/e2e_fixtures/001_auto_merge_off_batch.py
```

The file must export `def seed(db: Session) -> None`. Make it idempotent. After writing the fixture, re-run the seed inside the `app` container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell.** The host's `.env` resolves to the production orchestration DB on port 5433 — running `uv run python scripts/e2e_seed.py` outside a container will write test rows into the real DB.

If your verifications can't be satisfied with seed data alone, call `iw step-fail` with reason prefixed `ENV_DATA_MISSING:`.

## Verification Steps

### V1: Auto-merge toggle is visible on the create-batch-from-selection form

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/queue` (or wherever the seed exposes a list of approved items with a "Create batch from selection" action).
2. Select one or more approved items and trigger the "Create batch from selection" flow.
3. **Verify:** the batch creation form contains a checkbox or toggle labelled "Auto-merge" (or equivalent), and it is pre-filled to match the project's `auto_merge_default` (read the project's `projects.toml` entry to know which value to expect; iw-ai-core's default at design time is `true` if unset).
4. **Screenshot:** `ai-dev/active/CR-00036/evidences/post/CR-00036_v1_create_batch_form.png`.

### V2: Auto-merge value persists into the new batch

1. Submit the form with the toggle EXPLICITLY set to "off".
2. Navigate to the resulting batch's detail page Plan tab.
3. **Verify:** the Auto-merge value in the batch header reads "no" and the Plan-tab toggle is unchecked.
4. **Screenshot:** `ai-dev/active/CR-00036/evidences/post/CR-00036_v2_batch_plan_off.png`.

### V3: Plan-tab toggle is editable while the batch is pre-execution

1. Still on the new batch's Plan tab (status = `planning`).
2. Toggle the Auto-merge control to "on".
3. **Verify:** the page shows a success toast; the batch header refreshes to "Auto-merge: yes".
4. Reload the page to confirm persistence.
5. **Screenshot:** `ai-dev/active/CR-00036/evidences/post/CR-00036_v3_toggle_on.png`.

### V4: Plan-tab toggle is disabled while the batch is running

1. Find or seed an executing batch (status = `executing`).
2. Open its Plan tab.
3. **Verify:** the Auto-merge toggle is rendered with the HTML `disabled` attribute (and the existing max-parallel select is also disabled — this is a regression check).
4. **Screenshot:** `ai-dev/active/CR-00036/evidences/post/CR-00036_v4_toggle_disabled.png`.

### V5: Item detail page renders the Merge button when item is awaiting approval

1. Find or seed a BatchItem in `awaiting_merge_approval` state belonging to a batch with `auto_merge=false`. (If no fixture exists, add one — see "E2E DB seed data" above.)
2. Navigate to that item's detail page.
3. **Verify:**
   - The synthetic MERGE row in the Overview tab shows status "Awaiting approval" (or the equivalent label chosen in S07).
   - A **Merge** button is rendered next to the MERGE row.
   - Restart Merge / Abandon Merge buttons are NOT rendered for this item.
4. **Screenshot:** `ai-dev/active/CR-00036/evidences/post/CR-00036_v5_merge_button.png`.

### V6: Clicking Merge transitions the item out of awaiting_merge_approval

1. From V5, click the **Merge** button.
2. **Verify:**
   - A success toast appears ("Merge approved..." or equivalent).
   - The synthetic MERGE row's status changes (it may be `pending`, `in_progress`, or `completed` depending on daemon poll timing — any of these is acceptable; the key assertion is that `awaiting_approval` is gone).
   - The Merge button disappears.
3. **Screenshot:** `ai-dev/active/CR-00036/evidences/post/CR-00036_v6_merge_clicked.png`.

### V7: Auto-merge=true batch shows no Merge button (regression)

1. Find or seed a successfully completed BatchItem in a batch with `auto_merge=true` (i.e., a normal historical merge — should be plenty in the seed).
2. Navigate to its detail page.
3. **Verify:**
   - The MERGE row shows status "completed" (green checkmark).
   - No Merge button is rendered.
4. **Screenshot:** `ai-dev/active/CR-00036/evidences/post/CR-00036_v7_auto_merge_true.png`.

### V8: No Regressions

1. Visit the batches list, an arbitrary batch detail page (Items / Timeline / Logs tabs), an arbitrary item detail page, and the existing Restart Merge / Abandon Merge flows for an item with `merge_failed` status (if seed contains one).
2. **Verify:** no console errors on any page; existing buttons and links still work; status badges for unrelated statuses unchanged.
3. **Screenshot:** `ai-dev/active/CR-00036/evidences/post/CR-00036_v8_no_regressions.png`.

## Pass Criteria

All V1..V8 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason. There is no "mostly passed".

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. Use a normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly with HTTP 200 but the verification needed data not in the seed (e.g., V5 needs a BatchItem in `awaiting_merge_approval` and none exists). Add an `e2e_fixtures` file and prefix the reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V5 requires a BatchItem in awaiting_merge_approval — add ai-dev/active/CR-00036/e2e_fixtures/001_auto_merge_off_batch.py" \
    --report ai-dev/active/CR-00036/reports/CR-00036_S17_BrowserVerification_Report.md
  ```

## Report

Write `ai-dev/active/CR-00036/reports/CR-00036_S17_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V8.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if root cause was investigated.
- A list of the screenshots captured.
- A **No regressions observed** subsection covering V8.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00036/reports/CR-00036_S17_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00036/reports/CR-00036_S17_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "qv-browser",
  "work_item": "CR-00036",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "Toggle on create-batch form", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Auto-merge persists in new batch", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Plan-tab toggle editable pre-execution", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Plan-tab toggle disabled while running", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Merge button rendered on awaiting_approval", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Click Merge transitions out of awaiting_approval", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "auto_merge=true shows no Merge button", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V8", "name": "No regressions on adjacent flows", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
