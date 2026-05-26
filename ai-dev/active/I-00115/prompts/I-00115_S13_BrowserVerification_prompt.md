# Browser Verification Prompt: I-00115-S13-BrowserVerification

**Work Item**: I-00115 — Amend-scope modal locks the dashboard UI after dismissal
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

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

`docker compose exec app` to re-run the seed after writing a fixture
file is allowed and required (see "E2E DB seed data" below).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item touches NO migrations. Do not run any `alembic` command.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports, route paths, or credentials. Always use the env vars.

Before asserting on the *content* of any page, first confirm the page itself **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors). A 500 on the page that contains the element you're verifying is itself a `code_defect` finding.

Do NOT run: `make dev`, `make e2e-up`, any `docker compose up/down/restart/build`, `playwright install`, `agent-browser`, or `chromium.launch()`. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00115/I-00115_Issue_Design.md` — design document
- `dashboard/templates/components/scope_amend_modal.html` — post-S01 fixed template
- `tests/dashboard/test_scope_amend_modal_i00115.py` — post-S03 regression tests

## Output Files

- `ai-dev/active/I-00115/reports/I-00115_S13_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/I-00115/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with:

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

Rules:

1. Always call `playwright-cli snapshot` before `fill`/`click` to read the current accessible element IDs.
2. Wait for transitions to settle.
3. Screenshots go under `ai-dev/active/I-00115/evidences/post/` with descriptive filenames.

## E2E DB seed data

This verification needs a step in the `scope-blocked` state so the `✎ Amend scope` button appears. The production seed does NOT typically contain a live scope-blocked step. You MUST add a fixture file.

Create `ai-dev/active/I-00115/e2e_fixtures/001_scope_blocked_step.py` exporting:

```python
def seed(db: Session) -> None:
    """Idempotently insert a work item + step + step_run + fix_cycle that
    leaves the step in StepStatus.scope_blocked with one path violation.

    Pattern: copy the seed helpers from
    tests/integration/test_scope_amend_endpoints.py — the dataclass that
    builds a Project + WorkItem + WorkflowStep + StepRun + FixCycle with
    a FixTrigger.scope_violation entry. Adapt to a plain function. Use
    db.get(WorkItem, ...) before insert to make it idempotent.
    """
```

After writing the fixture, re-run the seed inside the `app` container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ NEVER run the seed from your host shell — `.env` resolves to the production orchestration DB on port 5433.

If you cannot reach the container or `scripts/e2e_seed.py` does not load fixture files from `ai-dev/active/I-00115/e2e_fixtures/`, call `iw step-fail` with `ENV_DATA_MISSING:` so the daemon recognizes it as an environment gap.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

Automatically prepended by the qv-browser agent. Documented for design reviewers.

The agent visits every distinct page route referenced in V1..Vn and:
- Extracts all fragment references (`hx-target="#X"`, `aria-controls="X"`, etc.) from the rendered HTML.
- Verifies each referenced `id="X"` is present.
- Reads `.playwright-cli/console-*.log` for unhandled JS/HTMX errors.
- Flags dangling references or unhandled load-time errors as V0 FAIL.

If V0 fails, V1..Vn still run. The V0 finding appears first in `--reason`.

### V1: Open the scope-amend modal

1. Navigate to the running-items page (find the link from the dashboard nav — "Running" / "System / Running"). Do NOT hardcode the path; click through the UI as a user would.
2. Locate the table row for the seeded scope-blocked step (item ID and step ID from the fixture you wrote).
3. Click the **✎ Amend scope** button on that row.
4. **Verify:** The modal opens. Snapshot shows both `#scope-amend-modal` and `#scope-amend-overlay` present. The modal title reads "Amend scope for <item-id> / <step-id>". The "Paths to add to scope" section lists at least one checkbox.
5. **Screenshot:** `ai-dev/active/I-00115/evidences/post/I-00115_v1_modal_open.png`.

### V2: Cancel button dismisses cleanly (baseline — was already working)

1. With the modal open from V1, snapshot to find the **Cancel** button ref.
2. Click **Cancel**.
3. **Verify (DOM):** After the click settles, take a snapshot. Neither `#scope-amend-modal` nor `#scope-amend-overlay` should appear. The page is fully interactive (try clicking a nav link — it should respond without page refresh).
4. **Screenshot:** `ai-dev/active/I-00115/evidences/post/I-00115_v2_cancel_clean.png`.

### V3: × close button dismisses cleanly (Defect 2 reproduction → fixed)

1. Re-open the modal (repeat V1 click).
2. Snapshot to find the **× Close modal** button ref.
3. Click **×**.
4. **Verify (DOM):** Both `#scope-amend-modal` AND `#scope-amend-overlay` are removed. The page is fully interactive. **CRITICAL:** before-fix, only the modal would be removed and the overlay would remain. If the snapshot still shows an overlay div with `.activity-modal-backdrop`, this is a `code_defect` — fail the step.
5. **Console check:** No `TypeError: Cannot read properties of null` in `.playwright-cli/console-*.log` from this click.
6. **Screenshot:** `ai-dev/active/I-00115/evidences/post/I-00115_v3_x_close_clean.png`.

### V4: Amend & restart dismisses cleanly on success (Defect 1 reproduction → fixed)

1. Re-open the modal (repeat V1 click).
2. Leave all checkboxes checked.
3. Snapshot to find the **Amend & restart** submit button ref.
4. Click **Amend & restart**.
5. **Verify (toast):** A success toast appears with text "scope amended" (the exact text comes from `_action_response` → `f"Step {step_id} scope amended ..."`).
6. **Verify (DOM):** Both `#scope-amend-modal` AND `#scope-amend-overlay` are removed after the POST returns. The page is fully interactive. **CRITICAL:** before-fix, the toast would appear but the modal+overlay would stay forever. If either remains, this is a `code_defect`.
7. **Verify (server side, OPTIONAL):** The step's status transitioned from `scope_blocked` to `pending` (visible in the table row's status badge updating, or via a dashboard refresh).
8. **Screenshot:** `ai-dev/active/I-00115/evidences/post/I-00115_v4_submit_clean.png`.

### V5: ESC key dismisses cleanly (new UX)

1. Re-seed if needed (V4 consumed the scope-blocked step — either re-run the fixture seed inside the container, or use a second pre-seeded step).
2. Open the modal (V1 click).
3. Press **Escape** key:
   ```bash
   playwright-cli press Escape
   ```
4. **Verify (DOM):** Both elements removed. Page interactive.
5. **Screenshot:** `ai-dev/active/I-00115/evidences/post/I-00115_v5_esc_clean.png`.

### V6: Backdrop click dismisses cleanly (new UX)

1. Re-seed if needed; open the modal again.
2. Snapshot. Click on the `#scope-amend-overlay` element directly (NOT on the modal body — find the overlay element ref from the snapshot).
3. **Verify (DOM):** Both elements removed.
4. **Verify (negative):** Re-open the modal once more. Click INSIDE the modal body (e.g. on the heading or a checkbox label). The modal MUST stay open — clicks inside the modal must not propagate to the backdrop dismissal handler. If the modal closes on an inside click, that is a `code_defect` (event propagation bug).
5. **Screenshot:** `ai-dev/active/I-00115/evidences/post/I-00115_v6_backdrop_clean.png`.

### V7: No Regressions

1. Revisit the running-items page. Click the **↩ Revert** button on a (different) scope-blocked step if one exists — confirm it still works (POST returns, toast appears). This was not changed by this fix; verify it didn't regress.
2. Revisit the item detail page for the item touched in V4 — confirm step status reflects the restart and the page renders without console errors.
3. Verify no new console errors appeared on any page visited during V1..V6.
4. **Screenshot:** `ai-dev/active/I-00115/evidences/post/I-00115_v7_no_regressions.png`.

## Pass Criteria

All V1..V7 must pass. Any failure — including partial or ambiguous results — requires `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps and spec mismatches

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but element/data missing because seed lacks it | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + add fixture |
| Page rendered cleanly, element correctly absent per design doc | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: ..."` |
| Page rendered cleanly, design says element should be present, it isn't | CODE_DEFECT | normal `--reason` |

The most likely fail mode here is V4 (modal+overlay remaining after submit) or V3 (overlay remaining after ×). Both are `code_defect`.

If the fixture seed fails to create a scope-blocked step (e.g. the daemon's fix_cycle helpers aren't reachable from a plain seed script), classify as `ENV_DATA_MISSING:` and add a SQL-only seed alternative.

### No cascading n/a — seed on demand

You MUST NOT write "blocked by V1 — n/a" chains. If the precondition cannot be satisfied with a fixture, write the row directly via the per-worktree DB.

## Report

Write `ai-dev/active/I-00115/reports/I-00115_S13_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V7.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if root cause was investigated.
- List of screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V7.

Then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00115/reports/I-00115_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00115/reports/I-00115_S13_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00115",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Open the scope-amend modal", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Cancel dismisses cleanly", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "× dismisses cleanly", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Amend & restart dismisses cleanly", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "ESC dismisses cleanly", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Backdrop click dismisses cleanly", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V7", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
