# I-00075 S13 Browser Verification Fix Cycle 5/5

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
- **Work item**: I-00075
- **Step**: S13

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | — | No dangling DOM references; console errors only favicon.ico 404 on initial load. |
| V1 | Fix-cycle amber pills render on I-99001 | **fail** | `code_defect` | `I-00075_v1_i99001_error.png` | I-99001 returns HTTP 500 due to `TypeError: not all arguments converted during string formatting` in `step_pipeline.html:18` — the `{}m{}s\|format(dur_m, dur_s)` Jinja2 expression receives integer values that cause a formatting mismatch. The fixture rows are correctly seeded (verified via direct DB query: 3 steps, 2 fix cycles on S02), but the page crashes before rendering. |
| V2 | No regression on zero-cycle item | pass | null | `I-00075_v2_cr00001_no_regression.png` | CR-00001 renders correctly with 0 fix-cycle pills. |
| V3 | No regressions on adjacent flows | pass | null | `I-00075_v3_batches_page.png` | Batches page renders correctly. History page shows I-99001 row correctly. |

## Console / Network Errors

- `http://localhost:9939/project/iw-ai-core/work/I-99001` → 404 (expected — route does not exist; `/item/` is the correct path)
- `http://localhost:9939/project/iw-ai-core/item/I-99001` → **500 Internal Server Error** (BUG — the item detail page crashes)
- favicon.ico 404 — benign, not a code defect

## Root Cause (V1 failure)

```
TypeError: not all arguments converted during string formatting
  dashboard/templates/components/step_pipeline.html:18
    {% set dur_str = "{}m{}s"|format(dur_m, dur_s) if dur_m > 0 else "{}s"|format(dur_s) %}
```

`dur_m` and `dur_s` are Python integers; Jinja2's `format` filter uses `%`-style formatting under the hood (`"{}m{}s" % (dur_m, dur_s)`), which does not accept integer arguments — it expects a tuple. The error only manifests when a `StepDetail` is constructed with integer `duration_secs` (which it always is, from line 457 of `items.py`).

The production pg_dump items likely have `NULL` for `started_at`/`completed_at` on their workflow steps (so `duration_secs` is never computed and `dur` stays `None`), which is why the bug was not caught before I-00075's fixture. The I-00075 fixture sets `started_at` and `completed_at` to `now`, making `dur` a non-None integer.

**Code location**: `dashboard/templates/components/step_pipeline.html:18`

## No Regressions

- V2 (CR-00001): Step pipeline renders with 0 `iw-pipeline-pill--fixcycle` elements — confirmed ✓
- V3 (batches/history): Batches page loads correctly; I-99001 appears in History table ✓

## Screenshots captured

- `ai-dev/active/I-00075/evidences/post/I-00075_v1_i99001_error.png` — V1 failure (HTTP 500 on I-99001 item detail)
- `ai-dev/active/I-00075/evidences/post/I-00075_v2_cr00001_no_regression.png` — V2 pass (CR-00001 renders without fix-cycle pills)
- `ai-dev/active/I-00075/evidences/post/I-00075_v3_batches_page.png` — V3 pass (batches page)

## Fixtures

The fixture `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` was **correctly loaded** — verified via direct DB query:
- `work_items` row: `('I-99001', 'iw-ai-core', 'Issue', 'completed', 'done')` ✓
- `workflow_steps`: 3 rows (S01, S02, S03) ✓
- `fix_cycles`: 2 rows on step S02 (cycle 1 and cycle 2) ✓

The V1 failure is **not** an `env_data_missing` — the fixture is present and the data is seeded correctly. The failure is a `code_defect` in the Jinja2 template that is now exposed by the fixture's non-null timestamps.

## Database Verification (direct query)

```python
# Steps for I-99001:
# (1, 'S01', 1, 'implementation', 'completed')
# (2, 'S02', 2, 'code_review', 'completed')
# (3, 'S03', 3, 'quality_validation', 'completed')

# Fix cycles for I-99001:
# (1, 2, 1, 'completed', 'S02')
# (2, 2, 2, 'completed', 'S02')
```

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


**ESCALATION**: This is the FINAL browser fix cycle (5/5). **PREFER honest escalation over a Hail-Mary fix that drifts from the design spec.** If you cannot make every failing V pass while staying aligned with the design doc above, document which V's remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
