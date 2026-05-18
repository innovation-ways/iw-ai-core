# Browser Verification Prompt: I-00090-S13-BrowserVerification

**Work Item**: I-00090 -- `/system/running` "Failed / Needs Attention" and "Recently Completed" tables show steps from inactive work items
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
infrastructure containers are outside your scope.

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. `docker compose exec app …` when re-running the seed script after
     writing an `e2e_fixtures/` file (the stack itself is already up).
  4. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp commands. This item
does not generate any migration.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide.

Do NOT hardcode application **route paths** either. The IW AI Core dashboard's routes for this verification are stable (`/system/running` and `/project/{id}/running`) and DO match the design doc, but if you get a 404 on either, classify it as a `spec_mismatch` (not a code defect) and report the path that DID work.

Before asserting on the *content* of any page, first confirm the page itself **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors). A 500 on the page that contains the table you're verifying is itself a `code_defect` finding.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any non-`exec` `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00090/I-00090_Issue_Design.md` -- the design document
- `ai-dev/active/I-00090/I-00090_Functional.md` -- functional summary
- `ai-dev/active/I-00090/evidences/pre/I-00090-bug-evidence.png` -- pre-fix screenshot (production, NOT the worktree stack)
- `dashboard/routers/running.py` -- the file modified by S01

## Output Files

- `ai-dev/active/I-00090/reports/I-00090_S13_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00090/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

The IW AI Core dashboard does NOT require login (it's an internal operator tool, no auth on `/system/*` or `/project/*` routes). You can skip the login dance — proceed directly to navigation.

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00090/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects current production state. Since the pre-fix screenshot was taken on the SAME production DB on 2026-05-17 and showed four stale rows (CR-00023, CR-00049, CR-00052, CR-00054), the worktree stack will start with the same four stale rows already present in the seed.

**This is exactly what you want for verification.** After the fix is applied, those four CRs MUST NOT appear in the Failed table. No fixture file is needed.

If for some reason the seed does NOT contain those CRs (e.g. they were archived between the design's snapshot and your run, causing the underlying `workflow_steps` rows to also be archived/cleaned up), classify the verification as `ENV_DATA_MISSING` and report which CR(s) are absent — do not fail the step as a code defect:

```bash
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "ENV_DATA_MISSING: V1 expects CR-00023/49/52/54 stale failed-step rows in seed but only X found — verify production state at time of seed" \
  --report ai-dev/active/I-00090/reports/I-00090_S13_BrowserVerification_Report.md
```

If, conversely, ONE OR MORE of the four CRs still appears in the Failed table after the fix, that is a CODE_DEFECT — the predicate did not exclude it. Capture which CR(s) remain.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> This verification is automatically prepended by the qv-browser agent before any work-item-specific V steps.

The agent will visit every distinct page route referenced in V1..V(n) and:

- Extract all fragment references (`hx-target="#X"`, `hx-include="#X"`, `aria-controls="X"`, `aria-labelledby="X"`, `href="#X"`, `for="X"`) from the rendered HTML via `curl`.
- Verify each referenced `id="X"` is present in the same HTML response.
- Read `.playwright-cli/console-*.log` after each page load to detect unhandled JS or HTMX errors.
- Flag any dangling reference or unhandled load-time error as a V0 FAIL.

### V1: `/system/running` Failed table excludes inactive CRs (primary reproduction)

1. Navigate to `$IW_BROWSER_BASE_URL/system/running`.
2. `playwright-cli snapshot` — confirm a region/heading text "Failed / Needs Attention" is present (the table itself may be empty, which is the EXPECTED post-fix state).
3. **Verify:** None of the strings `"CR-00023"`, `"CR-00049"`, `"CR-00052"`, `"CR-00054"` appears in the rendered page text within the "Failed / Needs Attention" section. The simplest check is to call `playwright-cli snapshot` and verify that the snapshot YAML does NOT mention those item IDs in the failed-table rowgroup (use `grep -E "CR-0002[3]|CR-0004[9]|CR-0005[24]"` against the snapshot file — exit 1 means PASS).
4. **Also verify:** the page returned HTTP 200, no exception page, no console errors.
5. **Screenshot:** save to `ai-dev/active/I-00090/evidences/post/I-00090_v1_system_running_failed_table.png` (use `playwright-cli screenshot` then `cp .playwright-cli/page-*.png …` to that path).

### V2: `/project/iw-ai-core/running` Failed table excludes the same CRs

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/running`.
2. `playwright-cli snapshot`.
3. **Verify:** same absence check as V1 — none of the four CR IDs appears in the Failed table region.
4. **Verify:** HTTP 200, no exception, no console errors.
5. **Screenshot:** `ai-dev/active/I-00090/evidences/post/I-00090_v2_project_running_failed_table.png`.

### V3: Active failing item (if any) STILL surfaces

1. Before V1, query the production DB seed (the worktree's per-worktree DB) for any work item whose `archived_at IS NULL` AND `status NOT IN ('completed','cancelled')` AND has at least one workflow_step with `status IN ('failed','needs_fix')`. If one exists, capture its ID as `$ALIVE_ITEM`.
   - Quickest method: `docker compose -p "$COMPOSE_PROJECT_NAME" exec db psql -U iw_core -d iw_core -c "SELECT wi.id FROM work_items wi JOIN workflow_steps ws ON ws.project_id=wi.project_id AND ws.work_item_id=wi.id WHERE wi.archived_at IS NULL AND wi.status NOT IN ('completed','cancelled') AND ws.status IN ('failed','needs_fix') LIMIT 1;"` — read the resulting id.
2. Navigate to `$IW_BROWSER_BASE_URL/system/running`.
3. **Verify:** if `$ALIVE_ITEM` exists, its ID DOES appear in the "Failed / Needs Attention" table region. If no active failing item exists in the seed, mark this verification `n/a` with a one-line justification (`"no active items have failed steps in current seed; AC2 covered by S03's unit tests"`) — this is acceptable because the helper-level tests already prove AC2 deterministically.
4. **Screenshot:** `ai-dev/active/I-00090/evidences/post/I-00090_v3_active_item_still_surfaces.png` (or skip if `n/a`).

### V4: "Recently Completed (last hour)" table excludes inactive items

1. Still on `$IW_BROWSER_BASE_URL/system/running`, locate the "Recently Completed (last hour)" section.
2. **Verify:** every item ID listed in that table is one whose underlying WorkItem is currently active. The seeded DB is a production snapshot — recent completions there belong to genuinely active or completing items, so the table SHOULD be sparse or contain only active-item rows.
3. If you observe a row whose item ID is one of the four stale CRs (CR-00023/49/52/54), that is a CODE_DEFECT for AC3.
4. **Screenshot:** `ai-dev/active/I-00090/evidences/post/I-00090_v4_recently_completed_filtered.png`.

### V5: No Regressions

1. Re-snapshot `$IW_BROWSER_BASE_URL/system/running` and verify the "Running Now" table is unchanged in structure (header row still present, sidebar badge still updates). The Running Now content is unchanged by this fix; it should look exactly as it did before.
2. Re-snapshot `$IW_BROWSER_BASE_URL/project/iw-ai-core/running` and verify the per-project sidebar links (Worktree Health, Container Health, System Status, etc.) still render — i.e. the layout shell is intact.
3. Verify no new console errors on any page visited during V1..V4.
4. **Screenshot:** `ai-dev/active/I-00090/evidences/post/I-00090_v5_no_regressions.png`.

## Pass Criteria

All V0..V5 must pass (V3 may be `n/a` per its own rule). Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps and spec mismatches

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw console exception | CODE_DEFECT | normal `--reason` |
| Stale CR still appears in Failed table after fix | CODE_DEFECT | normal `--reason` — the predicate didn't exclude it |
| Active failing item missing from Failed table | CODE_DEFECT | the predicate over-excluded |
| Seed does not contain the four stale CRs | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: …"` |
| Page rendered cleanly, V step asks for an element correctly absent per design | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: …"` |

The fix-cycle agent MUST NOT attempt code patches for SPEC_MISMATCH findings. The verification step itself needs to be corrected.

### No cascading `n/a` — seed on demand

Do NOT write "blocked by V2 — n/a" chains. V3 is the only legitimately-conditional verification (because the seed may not have an active failing item at the moment); every other V is unconditional.

## Report

After verification, write `ai-dev/active/I-00090/reports/I-00090_S13_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V0..V5.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if you investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering Running Now table and sidebar.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00090/reports/I-00090_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00090/reports/I-00090_S13_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00090",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "/system/running excludes inactive CRs", "status": "pass|fail", "failure_class": "code_defect|env_data_missing|null", "screenshot": "evidences/post/I-00090_v1_system_running_failed_table.png", "notes": ""},
    {"id": "V2", "name": "/project/iw-ai-core/running excludes inactive CRs", "status": "pass|fail", "failure_class": "code_defect|env_data_missing|null", "screenshot": "evidences/post/I-00090_v2_project_running_failed_table.png", "notes": ""},
    {"id": "V3", "name": "Active failing item still surfaces", "status": "pass|fail|n/a", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Recently Completed filtered", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "evidences/post/I-00090_v4_recently_completed_filtered.png", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "evidences/post/I-00090_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed or was legitimately `n/a` (V3 only).
- `overall_failure_class`: most severe across all Vs. `spec_mismatch` > `env_data_missing` > `code_defect`. `null` when `overall_status` is `pass`.
- `base_url_used`: substitute the concrete URL from `$IW_BROWSER_BASE_URL` before writing.
