# I-00075 S13 Browser Verification Fix Cycle 4/5

The end-to-end browser verification for step S13 of work item I-00075 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00075/ai-dev/active/I-00075/I-00075_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00075 S13 Browser Verification Report

## Environment
- **Base URL used**: `http://localhost:9939`
- **E2E user**: `dev@example.local`
- **Work Item**: I-00075
- **Step**: S13

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | — | History, batches, and fix-cycles tabs load without dangling DOM references or load-time JS errors |
| V1 | Fix-cycle amber pills render on I-99001 | **fail** | code_defect | — | `/project/iw-ai-core/item/I-99001/tab/overview` returns HTTP 500; fix-cycles tab works; 500 also on full item_detail page |
| V2 | No regression on zero-cycle item (I-00001) | pass | null | `I-00075_v2_no_regression_zero_cycle_item.png` | I-00001 renders cleanly; zero `iw-pipeline-pill--fixcycle` elements confirmed in HTML; no console errors |
| V3 | No regressions on adjacent flows | pass | null | `I-00075_v3_no_regressions.png` | Batches page and History page render correctly; I-99001 appears in History table |

## Console / Network Errors

- `I-99001/tab/overview` → HTTP 500 (Internal Server Error) — **page crashes, no amber pills verified**
- `I-99001` (full item page) → HTTP 500
- `I-00001/tab/overview` → HTTP 200 OK (no error)
- `I-99001/tab/fix-cycles` → HTTP 200 OK (fix cycles data loads correctly — proves fixture seeded FixCycle rows)
- `I-99001/step-runs/S02` → HTTP 200 OK (3 runs for S02 confirmed)
- Batches, History → HTTP 200 OK

Console error observed: `Timing middleware error: not all arguments converted during string formatting` — this is a pre-existing bug in `dashboard/utils/timing.py:94` (log format string mismatch) unrelated to the fix-cycle feature.

## Root Cause

**V1 fails with HTTP 500 on I-99001's overview tab.**

The error occurs inside `_get_cascade_history()` when computing `ItemMetrics` for the item header. The traceback shows an unhandled exception propagating through the middleware stack (alembic_guard → session_cookie → timing → router). The fix-cycles tab works correctly (HTTP 200, shows 2 FixCycle rows for S02), proving:
1. The fixture `001_fix_cycle_demo.py` **was loaded successfully** — FixCycle rows exist in the DB
2. The `_get_fix_cycles()` function works correctly
3. The `_get_cascade_history()` function (called only by the overview/tab/fix-cycles tabs that use cascade data) has a bug when handling I-99001's cascade state

The crash is **not** a missing fixture — `item_tab_overview` crashes because `_get_steps()` returns steps where the cascade history computation fails. I-00001 (with no FixCycle rows, no cascade events) renders fine.

The `item_header.html` template renders `metrics.fix_cycles_count` correctly (the Fix Cycles metric card on I-99001's header shows "2"), but the full tab render fails. This strongly suggests the crash is in the cascade history tree construction (lines ~1039–1068 in `items.py`) when processing I-99001's `DaemonsEvent` rows.

**This is a code defect in `_get_cascade_history`** — it raises an unhandled exception for the specific cascade history state of I-99001. The fix-cycle amber pill rendering code itself (`step_pipeline.html:33-41`) is never reached because the page crashes before the template renders.

## Screenshots Captured

- `ai-dev/active/I-00075/evidences/post/I-00075_v2_no_regression_zero_cycle_item.png`
- `ai-dev/active/I-00075/evidences/post/I-00075_v3_no_regressions.png`

## No Regressions

- **V2 (zero-cycle item)**: I-00001 renders correctly with `iw-pipeline-pill--pending` pills for S00 and MERGE only. Zero `iw-pipeline-pill--fixcycle` elements confirmed. No new console errors.
- **V3 (adjacent flows)**: Batches page loads with correct filter state. History page shows I-99001 at the top of the 4-item list alongside I-00001, F-00055, and CR-00001.

## Fixture Status

The fixture `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` **is loaded and working**:
- `/project/iw-ai-core/item/I-99001/tab/fix-cycles` returns HTTP 200 with 2 FixCycle entries for S02 (cycles 1 and 2)
- `/project/iw-ai-core/item/I-99001/step-runs/S02` returns 3 completed runs
- The Fix Cycles metric card in the item header correctly shows "2"

The verification failure is **not** due to missing fixture data — it is a code defect in `_get_cascade_history()` that prevents the overview tab from rendering for items with the specific cascade history state that I-99001 has.

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
