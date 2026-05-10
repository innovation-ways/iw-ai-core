# I-00075 S13 Browser Verification Fix Cycle 2/5

The end-to-end browser verification for step S13 of work item I-00075 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00075/ai-dev/active/I-00075/I-00075_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00075 S13 Browser Verification Report

## Environment
- **Base URL used**: `http://localhost:9939` (from `$IW_BROWSER_BASE_URL`)
- **E2E user**: `dev@example.local`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | fail | code_defect | — | Pages I-99001 and CR-00001 both hit errors on initial navigation |
| V1 | Fix-cycle amber pills render on I-99001 | fail | code_defect | I-00075_v1_fix_cycle_amber_pills.png | I-99001 returns HTTP 500 — TypeError in step_pipeline.html:20 |
| V2 | No regression on zero-cycle item | pass | null | I-00075_v2_no_regression_zero_cycle_item.png | CR-00001 renders cleanly; zero fix-cycle pills confirmed |
| V3 | No regressions on adjacent flows | pass | null | I-00075_v3_no_regressions.png | Batches and History pages render without errors |

## Console / Network Errors

| Page | Error |
|------|-------|
| `GET /project/iw-ai-core/work/I-99001` | 404 — route does not exist (wrong URL format) |
| `GET /project/iw-ai-core/item/I-99001` | 500 Internal Server Error — `TypeError: not all arguments converted during string formatting` in `step_pipeline.html:20` |
| `GET /project/iw-ai-core/item/CR-00001` | None (clean) |
| `GET /project/iw-ai-core/batches` | None (clean) |
| `GET /project/iw-ai-core/history` | None (clean) |

## Root Cause

**`dashboard/templates/components/step_pipeline.html:20`**:

```jinja
{% set dur_str = "{}m{}s"|format(dur_m, dur_s) if dur_m > 0 else "{}s"|format(dur_s) %}
```

When `dur_m == 0` (true for all steps in the fixture, which have `duration_secs = None` → `dur_m = 0`, `dur_s = 0`), the Jinja2 conditional expression is evaluated as a single unit. Python's `str.format()` tries to fill the `{}` placeholder in `"{}s"` with the full `dur_s` value (the integer `0`), but the format string only has one placeholder — so the operation raises `TypeError: not all arguments converted during string formatting`.

This is a **code defect** in `step_pipeline.html` — the template unconditionally assumes `dur_s` will always be a positive integer when `dur_m == 0`. The fix requires computing `dur_s` from `duration_secs % 60` even when `dur_m == 0`, or restructuring the conditional to avoid calling `format()` in the `else` branch when `duration_secs` is `None`/`0`.

The fixture data (`I-99001`) is **correct** (confirmed present in the History page with the expected title), but the render path crashes before the amber pills can be displayed.

## Screenshots Captured

- `ai-dev/active/I-00075/evidences/post/I-00075_v1_fix_cycle_amber_pills.png` — I-99001 500 error page
- `ai-dev/active/I-00075/evidences/post/I-00075_v2_no_regression_zero_cycle_item.png` — CR-00001 rendered cleanly
- `ai-dev/active/I-00075/evidences/post/I-00075_v3_no_regressions.png` — Batches page

## No Regressions Observed

- **V2 (CR-00001)**: Step pipeline renders correctly with 0 fix-cycle pills. The `iw-pipeline-pill--fixcycle` class does NOT appear. The render branch at `step_pipeline.html:33-41` correctly skips when `fix_cycle_count == 0`.
- **V3 (batches + history)**: Both pages load without console errors. History correctly shows `I-99001` as the first item (fixture seeded successfully). The page structure is intact.

## Key Evidence

1. **I-99001 exists in DB**: History page shows `I-99001 Issue Fix-cycle demo (I-00075 fixture) completed May 09 —` as the first row.
2. **I-99001 crashes on item_detail**: HTTP 500 with `TypeError: not all arguments converted during string formatting` at `step_pipeline.html:20`.
3. **CR-00001 renders cleanly**: HTTP 200, no console errors, zero amber pills — confirming the non-fixture path is healthy.

## Fix Required

The `step_pipeline.html` template needs to handle the case where `duration_secs` is `None` or `0` without calling `format()` on an incompatible type. The simplest fix:

```jinja
{% if dur_str is not none and dur_str != '' %}
  {{ dur_str }}
{% else %}
  —
{% endif %}
```

with `dur_str` computed as:
```jinja
{% if step.duration_secs is not none %}
  {% set dur_m = (step.duration_secs // 60)|int %}
  {% set dur_s = (step.duration_secs % 60)|int %}
  {% set dur_str = "{}m{:02d}s"|format(dur_m, dur_s) if dur_m > 0 else "{}s"|format(dur_s) %}
{% else %}
  {% set dur_str = none %}
{% endif %}
```

This ensures `format()` is only called when `duration_secs` is guaranteed to be a positive integer.

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
