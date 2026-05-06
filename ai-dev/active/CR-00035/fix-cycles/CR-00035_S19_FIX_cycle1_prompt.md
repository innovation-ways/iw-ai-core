# CR-00035 S19 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S19 of work item CR-00035 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00035/ai-dev/active/CR-00035/CR-00035_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# CR-00035 S19 QV: Unit Tests — Report

## What Was Done
Executed `make test-unit` as the gate command for step S19.

## Result: FAIL

**Exit code**: 1 (test failure)

## Failure Summary

| Item | Detail |
|------|--------|
| Gate | `make test-unit` |
| Exit code | 1 |
| Total tests | 2620 passed, 1 failed, 4 skipped, 5 xfailed, 1 xpassed |
| Duration | 57.81s |
| Coverage | 52.62% (required: 46.0%) ✓ |

## Failed Test

```
tests/unit/test_smoke.py::TestSmokePlatformBasics::test_root_projects_page_renders
```

**Root cause**: The test imports `dashboard.app.create_app()` which, during app factory construction (`dashboard/app.py:77`), calls `verify_instance_identity(session)`. This check compares the live DB's `instance_id` against `IW_CORE_EXPECTED_INSTANCE_ID` in `.env`.

The test sets `IW_CORE_OPERATOR_APPLY=true` to bypass the live-DB guard during module imports, but `verify_instance_identity` is called *inside* the app factory (after the guard bypass), and it queries the *actual live DB at port 5433* — not a testcontainer. The live DB has instance ID `5c976107-5c80-43a4-af87-37849030b392` but `.env` expects `08446ded-daba-4e08-9721-3046dc68efa0`.

**Error**:
```
orch.db.identity.InstanceMismatchError: DB instance-identity MISMATCH.
  Expected: 08446ded-daba-4e08-9721-3046dc68efa0   (from IW_CORE_EXPECTED_INSTANCE_ID)
  Actual  : 5c976107-5c80-43a4-af87-37849030b392   (from iw_core_instance.instance_id)
```

## Classification: ENV_DATA_MISSING (Test Isolation Issue)

This is not a code defect in CR-00035. The test `test_root_projects_page_renders` is not properly isolated from the live DB — it reaches the live DB despite the `IW_CORE_OPERATOR_APPLY=true` bypass. The test was written to verify the dashboard app factory works (app creates, routes exist), but the identity check happens after the operator-apply bypass window, causing a live DB connection.

## Environment Verification
- `IW_CORE_EXPECTED_INSTANCE_ID` in `.env`: `08446ded-daba-4e08-9721-3046dc68efa0`
- Live DB instance ID: `5c976107-5c80-43a4-af87-37849030b392`
- `iw db-identity check`: OK (matches expected)
- This worktree's `.env` and the live DB are out of sync — this is a pre-existing environment issue, not a CR-00035 regression.

## Verdict
The gate failed due to an environment/test-isolation issue, not a defect in CR-00035's changes. The 1 failing test is `test_root_projects_page_renders` which cannot pass in this worktree due to the live DB identity mismatch.


## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: 1 smoke test fails due to live DB instance_id mismatch — test_root_projects_page_renders hits verify_instance_identity which queries live DB (actual: 5c976107, expected in .env: 08446ded). This is a pre-existing environment/test-isolation issue, not a code defect in CR-00035.

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/CR-00035/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S19` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00035/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00035/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
