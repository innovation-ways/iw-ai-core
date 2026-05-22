# I-00103 S16 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S16 of work item I-00103 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/daemon/auto_merge.py
  dashboard/templates/fragments/auto_merge_event_detail.html
  tests/integration/test_auto_merge_failed_event_metadata.py
  tests/dashboard/test_auto_merge_event_detail_per_file_errors.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00103/ai-dev/active/I-00103/I-00103_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00103 S16 Browser Verification Report

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string  
**Step**: S16  
**Agent**: qv-browser  
**Date**: 2026-05-22  
**Base URL Used**: `http://localhost:9926`

## Status Summary

| Verification | ID | Status | Failure Class | Notes |
|---|---|---|---|---|
| Pre-flight page sanity | V0 | FAIL | ENV_DATA_MISSING | E2E stack healthy at env-up, but containers no longer running |
| per_file_errors visible (AC3) | V1 | FAIL | ENV_DATA_MISSING | Cannot verify — E2E stack not available |
| Historical event renders without section (AC4) | V2 | FAIL | ENV_DATA_MISSING | Cannot verify — E2E stack not available |
| No regressions | V3 | FAIL | ENV_DATA_MISSING | Cannot verify — E2E stack not available |

## Console Errors Observed

1. `[ERROR] htmx:afterRequest` — network error on `/system/nav/worktree-badge`
2. `[ERROR] htmx:sendError` — network error
3. `[ERROR] Failed to load resource: net::ERR_CONNECTION_REFUSED` — `/system/nav/worktree-badge:0`

## Screenshots Captured

None — the E2E stack was not accessible at the time of verification.

## What Was Attempted

1. **Environment probe**: Confirmed `IW_BROWSER_BASE_URL=http://localhost:9926` from environment.
2. **Stack status check**: Docker containers for `iw-ai-core-e2e-i00103-*` were not found — no containers running with that prefix.
3. **Browser open attempt**: `playwright-cli open http://localhost:9926` returned `ERR_CONNECTION_REFUSED`.
4. **Log review**: `ai-dev/logs/I-00103_S16_browser_env_up.log` shows the E2E stack WAS successfully brought up (`[e2e_up] stack healthy`), meaning the stack was running at some point during the step's lifecycle but was cleaned up before the browser agent could execute verification.
5. **Fixture creation**: Wrote `ai-dev/active/I-00103/e2e_fixtures/001_seed_failed_event_with_per_file_errors.py` — fixture is ready for use once the E2E environment is re-available.

## Root Cause

The E2E stack (daemon-managed via `scripts/e2e_up.sh`) was successfully provisioned and healthy at the time of env-up, but the containers were subsequently stopped/removed. This was likely due to:
- A daemon-level timeout on the browser verification step releasing the environment before this agent could complete, OR
- The step's execution window expired and the daemon cleaned up the environment.

The step was already in `in_progress` state when this agent started, suggesting a prior agent instance had already begun work but the environment timed out.

## Environment Data

- `IW_BROWSER_BASE_URL`: `http://localhost:9926`
- `IW_BROWSER_E2E_USER`: `dev@example.local`
- `IW_BROWSER_E2E_PASSWORD`: `DevPass2026!`
- `IW_ITEM_ID`: `I-00103`
- `IW_STEP_ID`: `S16`
- E2E compose project: `iw-ai-core-e2e-i00103`

## No Regressions Observed

Not applicable — no browser verification could be performed due to environment unavailability.

## Classification

**ENV_DATA_MISSING**: The E2E stack was healthy at env-up time but unavailable at execution time. The fixture file has been prepared for the next attempt.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "I-00103",
  "overall_status": "fail",
  "overall_failure_class": "env_data_missing",
  "base_url_used": "http://localhost:9926",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "fail", "failure_class": "env_data_missing", "screenshot": "", "notes": "E2E stack not running - containers gone, connection refused"},
    {"id": "V1", "name": "per_file_errors visible (AC3)", "status": "fail", "failure_class": "env_data_missing", "screenshot": "", "notes": "Cannot verify - E2E stack unavailable"},
    {"id": "V2", "name": "historical event renders without section (AC4)", "status": "fail", "failure_class": "env_data_missing", "screenshot": "", "notes": "Cannot verify - E2E stack unavailable"},
    {"id": "V3", "name": "no regressions", "status": "fail", "failure_class": "env_data_missing", "screenshot": "", "notes": "Cannot verify - E2E stack unavailable"}
  ],
  "console_errors_observed": [
    "htmx:afterRequest network error",
    "htmx:sendError",
    "ERR_CONNECTION_REFUSED on /system/nav/worktree-badge"
  ],
  "screenshots": [],
  "notes": "Stack was healthy at env-up (per logs) but containers were gone by execution time. Fixture prepared at ai-dev/active/I-00103/e2e_fixtures/001_seed_failed_event_with_per_file_errors.py"
}
```

## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: E2E stack healthy at env-up (logs confirm) but containers not running at execution time. Connection refused on http://localhost:9926.

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/I-00103/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S16` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00103/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00103/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
