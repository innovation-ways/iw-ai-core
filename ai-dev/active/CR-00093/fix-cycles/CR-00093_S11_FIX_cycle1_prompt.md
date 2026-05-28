# CR-00093 S11 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S11 of work item CR-00093 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  .iw-orch.json
  ai-dev/work/TESTS_ENHANCEMENT.md

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/CR-00093/**
  ai-dev/archive/CR-00093/**
  ai-dev/work/CR-00093/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00093/ai-dev/active/CR-00093/CR-00093_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# CR-00093 S11 Browser Verification Report

- Work item: CR-00093
- Step: S11
- Base URL used: `http://localhost:9951`
- Overall status: **FAIL**
- Failure class: **ENV_DATA_MISSING**
- Reason: Tests page shows **"No Test Configuration"** (`project.config.test_config` missing in E2E stack), so configured categories from `.iw-orch.json` were not synced into this stack.

## Verification Status

| ID | Name | Status | Notes | Screenshot |
|---|---|---|---|---|
| V0 | Pre-flight page sanity | pass | Home/project pages rendered without visible JS errors | |
| V1 | Tests page shows ≥24 cards | fail | Page rendered "No Test Configuration" instead of launch cards | `ai-dev/active/CR-00093/evidences/post/CR-00093_v1_tests_page_no_config_env_data_missing.png` |
| V2 | Quality page shows ≥13 cards | not-run | Blocked by ENV_DATA_MISSING prerequisite failure | |
| V3 | Smoke launch creates TestRun row | not-run | Blocked | |
| V4 | check-column-docs launch creates quality run row | not-run | Blocked | |
| V5 | e2e_stack mutual exclusion | n/a | Blocked | |
| V6 | No regressions on existing cards | not-run | Blocked | |

## Observed counts

- `tests_page_card_count`: `0` (no launch cards; config missing)
- `quality_page_card_count`: `n/a`

## TestRun IDs

- V3: `n/a`
- V4: `n/a`

## Screenshots

- `ai-dev/active/CR-00093/evidences/post/CR-00093_v1_tests_page_no_config_env_data_missing.png`

## Notes

Per step instructions, this is an orchestrator/environment sync issue (stack did not re-read `.iw-orch.json`) rather than a code defect.


## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: stack did not re-read .iw-orch.json (Tests page shows No Test Configuration)

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/CR-00093/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S11` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00093/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00093/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
