# Browser Verification Prompt: I-00112-S18-BrowserVerification

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step**: S18
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network state-change command. Testcontainers via pytest fixtures are the only exception; read-only `docker ps/inspect/logs` is fine. `docker compose exec app …` is allowed when re-running the seed after writing a fixture. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB. The orchestrator already applied migrations as part of stack provisioning. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. Do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Do NOT hardcode route paths beyond the ones documented below — `/system/keep-alive` is the canonical route and is part of the design. Use `playwright-cli` exclusively (not `agent-browser`, not direct `chromium.launch()`).

Do NOT run `make dev`, `make e2e-up`, `docker compose up/down/restart/build`, or `playwright install` — the stack is up and the CLI is pre-installed.

## Input Files

- `ai-dev/active/I-00112/I-00112_Issue_Design.md` — the design document.
- `ai-dev/active/I-00112/evidences/pre/I-00112-recent-executions-table.png` — pre-fix evidence (3-column table; every row "Success").
- Files modified by S05 (Frontend):
  - `dashboard/templates/fragments/keep_alive_runs.html`
  - possibly `dashboard/templates/_partials/help/keep_alive.html`
  - possibly `dashboard/static/styles.css`

## Output Files

- `ai-dev/active/I-00112/reports/I-00112_S18_BrowserVerification_Report.md` — mandatory report.
- `ai-dev/active/I-00112/evidences/post/` — screenshots taken during verification.

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
playwright-cli snapshot
```

The dashboard does not require login (the keep-alive page is open to localhost). If a login form appears (because the E2E stack stub-protects it), fill it with `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD` first.

## E2E DB seed data

The E2E stack's Postgres is seeded from the production orch DB via `pg_dump`. After the S01 migration is applied, the seeded `keep_alive_runs` rows will have NULL in the four new diagnostic columns — exactly the legacy-row case we need to exercise in V2.

If for any reason the seeded DB has no `keep_alive_runs` rows at all, write a fixture file:

```python
# ai-dev/active/I-00112/e2e_fixtures/001_legacy_keep_alive_run.py
from sqlalchemy.orm import Session
from orch.db.models import KeepAliveRun

def seed(db: Session) -> None:
    if db.query(KeepAliveRun).count() > 0:
        return
    db.add(KeepAliveRun(
        slot_id=None,
        slot_time="05:00",
        status="success",
        error=None,
        # stdout/stderr/elapsed_ms/returncode left NULL — legacy-row shape
    ))
    db.commit()
```

Then re-run the seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell** — the host's `.env` resolves to the production orch DB on port 5433.

For V3, write a second fixture file that inserts a populated row (`stdout="OK"`, `elapsed_ms=3500`, `returncode=0`, `status="success"`) so the populated-rendering path is exercised.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

The agent automatically visits every distinct route in V1..Vn, extracts htmx fragment refs and id="X" anchors, verifies each referenced id is present, and reads the console log for unhandled JS/HTMX errors. V0 failure does not skip V1..Vn; `overall_status` is `fail` if V0 fails and the V0 finding appears first in `--reason`.

### V1: Recent Executions table has the new column headers

1. Navigate to `${IW_BROWSER_BASE_URL}/system/keep-alive`.
2. Wait for the page to settle (htmx fragment for the runs table loads asynchronously — give it 2 seconds).
3. **Verify:** The Recent Executions table has exactly five column headers, in order: `Fired At`, `Slot`, `Status`, `Elapsed`, `Output`.
4. **Capture an evidence screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00112/evidences/post/I-00112_v1_columns_present.png`.

How to assert via snapshot: `playwright-cli snapshot` returns YAML with `columnheader "Elapsed" [ref=…]` and `columnheader "Output" [ref=…]` entries. Both must be present.

### V2: Legacy rows render `—` in new columns without crashing

1. Still on `${IW_BROWSER_BASE_URL}/system/keep-alive`.
2. **Verify:** At least one row in the Recent Executions table shows `—` in the **Elapsed** column AND `—` in the **Output** column. This proves the NULL-handling guards work on rows captured before the S01 migration. The row's other cells (Fired At, Slot, Status) MUST still render normally.
3. **Verify:** No JS console errors appear in `.playwright-cli/console-*.log` after the table renders.
4. **Capture an evidence screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00112/evidences/post/I-00112_v2_legacy_em_dash.png`.

### V3: Populated rows show elapsed_ms and stdout snippet

1. If the seeded DB has no row with non-NULL diagnostic fields, write the populated-row fixture described in "E2E DB seed data" above and re-run the seed.
2. Refresh `${IW_BROWSER_BASE_URL}/system/keep-alive`.
3. **Verify:** At least one row shows a numeric value followed by ` ms` in the **Elapsed** column (e.g. `3500 ms`).
4. **Verify:** That same row's **Output** column shows a non-empty model reply snippet (first ~80 chars of `stdout`).
5. **Verify:** Hovering the output cell (or inspecting the rendered HTML) reveals a `title` attribute containing the full stdout. Use `playwright-cli snapshot` to confirm the `title` is present on the relevant element.
6. **Capture an evidence screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00112/evidences/post/I-00112_v3_populated_row.png`.

### V4: No Regressions — adjacent flows still work

1. On the same page, exercise the existing slot-management controls:
   - Click an **Add Slot** button if one is visible (do NOT submit — just confirm the input becomes focusable / the modal opens without errors).
   - Inspect the **Coverage Timeline** section. Verify the colored slot blocks still render and the legend (00:00 / 06:00 / 12:00 / 18:00 / 24:00) is intact.
   - Inspect the **Configuration** section. Verify the **Claude Model** dropdown still lists `claude-sonnet-4-6` and `claude-opus-4-7`.
2. Navigate to one other system route (e.g. `${IW_BROWSER_BASE_URL}/system/status`) and back to `/system/keep-alive`. The runs table should re-render correctly with the new columns intact.
3. **Verify:** No new JS console errors appear during V1..V4 (re-check `.playwright-cli/console-*.log`).
4. **Capture an evidence screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00112/evidences/post/I-00112_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps and spec mismatches

- **CODE_DEFECT** — page returned 5xx, threw a console exception, rendered the wrong column header, or crashed the template on NULL fields. Use normal `--reason`.
- **ENV_DATA_MISSING** — page rendered cleanly but the seeded DB has no `keep_alive_runs` rows so V2 cannot observe the legacy `—` render. Prefix with `ENV_DATA_MISSING:` and either add the fixture described above (and re-seed) or fail with the prefixed reason if re-seed fails.
- **SPEC_MISMATCH** — page rendered cleanly, fewer columns than V1 expects, but design doc says column set is correct as-is. Prefix with `SPEC_MISMATCH:` and cite the design doc location.

### No cascading `n/a`

If V2 cannot find a legacy NULL row, the agent MUST attempt to create one via the fixture path before reporting `n/a`. Same for V3's populated row.

## Report

Write `ai-dev/active/I-00112/reports/I-00112_S18_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V4.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of screenshots captured.
- A **No regressions observed** subsection covering the adjacent flows in V4.

Then:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00112/reports/I-00112_S18_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00112/reports/I-00112_S18_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S18",
  "agent": "qv-browser",
  "work_item": "I-00112",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Recent Executions has Elapsed and Output column headers", "status": "pass|fail", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "evidences/post/I-00112_v1_columns_present.png", "notes": ""},
    {"id": "V2", "name": "Legacy NULL rows render em-dash without crash", "status": "pass|fail", "failure_class": "code_defect|env_data_missing|null", "screenshot": "evidences/post/I-00112_v2_legacy_em_dash.png", "notes": ""},
    {"id": "V3", "name": "Populated rows show elapsed_ms and stdout snippet", "status": "pass|fail", "failure_class": "code_defect|env_data_missing|null", "screenshot": "evidences/post/I-00112_v3_populated_row.png", "notes": ""},
    {"id": "V4", "name": "No regressions on adjacent flows", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "evidences/post/I-00112_v4_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/I-00112/evidences/post/I-00112_v1_columns_present.png",
    "ai-dev/active/I-00112/evidences/post/I-00112_v2_legacy_em_dash.png",
    "ai-dev/active/I-00112/evidences/post/I-00112_v3_populated_row.png",
    "ai-dev/active/I-00112/evidences/post/I-00112_v4_no_regressions.png"
  ],
  "notes": ""
}
```
