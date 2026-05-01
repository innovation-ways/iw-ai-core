# I-00059 S11 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S11 of work item I-00059 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00059/ai-dev/active/I-00059/I-00059_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00059 S11 Browser Verification Report

## Environment
- Base URL used: http://localhost:9919
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Error block visible | n/a | — | Job not found in DB (ENV_DATA_MISSING) |
| V2 | Parameters card shows skill_used/duration | n/a | — | Job not found in DB (ENV_DATA_MISSING) |
| V3 | View document link present | n/a | — | Job not found in DB (ENV_DATA_MISSING) |
| V4 | No regressions — jobs list | n/a | — | Could not navigate to job detail (ENV_DATA_MISSING) |

## Console / Network Errors
- GET `/project/iw-ai-core/jobs/doc_generation/2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435` → 404 "Job '2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435' not found"
- GET `/favicon.ico` → 404 (harmless, always occurs)

## Root Cause
**ENV_DATA_MISSING**: The job `2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435` (status=failed, error="generation timeout after 15 minutes", skill_used="iw-doc-generator", duration_seconds=600, doc_id="iw-ai-core:code-index") was expected to be seeded from production via `pg_dump`, but it is absent from the E2E DB. The job page returns `{"detail":"Job '2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435' not found"}`. No E2E fixture was present at `ai-dev/active/I-00059/e2e_fixtures/001_i00059_doc_job.py`. The stack must be re-provisioned with the fixture in place.

## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: Job 2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435 not found in E2E DB — production seed did not include it; no fixture at ai-dev/active/I-00059/e2e_fixtures/001_i00059_doc_job.py

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/I-00059/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S11` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00059/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00059/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
