# I-00075 S13 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S13 of work item I-00075 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00075/ai-dev/active/I-00075/I-00075_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00075 S13 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9939` (from `$IW_BROWSER_BASE_URL` env)
- E2E user: `dev@example.local`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | fail | code_defect | — | See below |
| V1 | Fix-cycle amber pills render on I-99001 | n/a | env_data_missing | — | E2E stack for I-00075 does not exist |
| V2 | No regression on zero-cycle item | n/a | env_data_missing | — | E2E stack for I-00075 does not exist |
| V3 | No regressions on adjacent flows | n/a | env_data_missing | — | E2E stack for I-00075 does not exist |

## Console / Network Errors

**V0 findings**:
- `http://localhost:9939` — `ERR_CONNECTION_REFUSED` (port not listening)
- The only service on the host mapped to port 9900 is `iwcore-173-app-1` at `localhost:53552` (via Docker port 53552→9900). Port 9939 is not open on any container or process.
- All container investigation confirms there is **no I-00075 E2E stack** running. Only `iwcore-173` is present (it's the most recent but is not the I-00075 stack — its DB has no `I-99001` row: `{"detail":"Work item 'I-99001' not found"}`).

## No Regressions Observed

V2/V3 could not be attempted — the isolated I-00075 E2E stack does not exist.

## Root Cause

**The orchestrator did not start the I-00075 E2E stack.** The `iwcore-172-app-1` container that was supposed to be the I-00075 stack crashed during Alembic migration with:
```
ERROR [alembic.util.messaging] Can't locate revision identified by 'a1b2c3fixmm'
FAILED: Can't locate revision identified by 'a1b2c3fixmm'
```
Exit code 255. The stack is not running.

The `iwcore-173-app-1` (a different worktree's stack) is live at port 53552 but its DB was pg_dump-seeded from production and does not contain the I-00075 fixture rows.

**Pre-flight V0 fails** because the base URL `http://localhost:9939` is unreachable — the E2E stack never launched.

## Screenshots captured

None — no browser session could reach the E2E stack.

## Subagent Result

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00075",
  "overall_status": "fail",
  "overall_failure_class": "env_data_missing",
  "base_url_used": "http://localhost:9939",
  "verifications": [
    {
      "id": "V0",
      "name": "Pre-flight page sanity",
      "status": "fail",
      "failure_class": "code_defect",
      "screenshot": "",
      "notes": "Port 9939 not reachable — iwcore-172-app-1 (the I-00075 E2E stack) crashed with 'Can't locate revision: a1b2c3fixmm'. Stack is not running."
    },
    {
      "id": "V1",
      "name": "Fix-cycle amber pills render on I-99001",
      "status": "n/a",
      "failure_class": "env_data_missing",
      "screenshot": "",
      "notes": "E2E stack does not exist; cannot navigate to /item/I-99001"
    },
    {
      "id": "V2",
      "name": "No regression on zero-cycle item",
      "status": "n/a",
      "failure_class": "env_data_missing",
      "screenshot": "",
      "notes": "E2E stack does not exist"
    },
    {
      "id": "V3",
      "name": "No regressions on adjacent flows",
      "status": "n/a",
      "failure_class": "env_data_missing",
      "screenshot": "",
      "notes": "E2E stack does not exist"
    }
  ],
  "console_errors_observed": [
    "ERR_CONNECTION_REFUSED at http://localhost:9939 (port not listening)"
  ],
  "screenshots": [],
  "notes": "iwcore-172-app-1 crashed on alembic migration with 'Can't locate revision: a1b2c3fixmm' (exit 255). I-00075 E2E stack never came up. iwcore-173 is live at port 53552 but is a different worktree and its DB lacks I-99001 rows. Orchestrator needs to re-provision the I-00075 E2E stack after fixing the alembic revision issue."
}
```

## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: I-00075 E2E stack (iwcore-172-app-1) crashed on alembic migration with 'Can't locate revision: a1b2c3fixmm' (exit 255). Port 9939 is not reachable. Stack was never provisioned. Orchestrator must re-provision after fixing the alembic revision issue.

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/I-00075/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S13` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00075/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00075/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
