# F-00090 S16 Browser Verification Fix Cycle 2/5

The end-to-end browser verification for step S16 of work item F-00090 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/db/models.py
  orch/db/migrations/versions/**
  orch/regression_link_service.py
  orch/cli/**
  dashboard/routers/items.py
  dashboard/routers/batches.py
  dashboard/routers/project_dashboard.py
  dashboard/templates/fragments/**
  dashboard/templates/pages/**
  dashboard/static/styles.css
  scripts/backfill_regression_classification.py
  tests/integration/test_regression_link_service.py
  tests/integration/test_backfill_regression_classification.py
  tests/dashboard/test_regression_classification_form.py
  tests/dashboard/test_quality_kpis_section.py
  docs/IW_AI_Core_Testing_Strategy.md
  docs/IW_AI_Core_Database_Schema.md
  docs/IW_AI_Core_Dashboard_Design.md
  skills/iw-ai-core-testing/**
  .claude/skills/iw-ai-core-testing/**
  ai-dev/work/TESTS_ENHANCEMENT.md
  docs/IW_AI_Core_CLI_Spec.md
  tests/integration/test_cli_spec_conformance.py
  dashboard/templates/_partials/help/quality-kpis.html

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/F-00090/**
  ai-dev/archive/F-00090/**
  ai-dev/work/F-00090/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/ai-dev/active/F-00090/F-00090_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# F-00090 S16 Browser Verification Report

- Base URL used: `http://localhost:9923`
- Work item / step: `F-00090` / `S16`

## Verification Results

| ID | Verification | Status | Notes |
|---|---|---|---|
| V1 | Classification form renders on Incident detail page | PASS | `I-00990` detail shows Regression classification section, searchable work-item picker, commit SHA placeholder, 3 radios (regression/pre-existing/unknown), enabled Save button. |
| V2 | Quality KPIs section shows at least one classified regression | PASS | Dashboard + `/project/iw-ai-core/quality-kpis` show merges/regressions/rate, trend chart, week row `2026-W22` with regressions `1`, no `NaN`. |
| V3 | Regression badge appears on Batches/History row | PASS | History row `F-00990` shows badge `1 regression` with `iw-regression-badge`. |
| V4 | Empty-state for project with no merges | N/A | No zero-merge project exists in current seed set (only `iw-ai-core`). |
| V5 | No regressions | FAIL | Console log contains repeated HTMX `sendError` / `ERR_CONNECTION_REFUSED` for `/projects/iw-ai-core/staleness-dot` and `/system/nav/worktree-badge`. |

## Issues Found

1. **Console/runtime errors during visited flows** (`CODE_DEFECT`)
   - Evidence: `.playwright-cli/console-2026-05-27T19-20-42-854Z.log:1` (and many subsequent lines)
   - Symptoms: repeated `htmx:afterRequest`, `htmx:sendError`, and `Failed to load resource: net::ERR_CONNECTION_REFUSED`.
   - Affected endpoints include `/projects/iw-ai-core/staleness-dot`, `/system/nav/worktree-badge`, `/api/usage/llm/fragment`.

## Screenshots

- `ai-dev/active/F-00090/evidences/post/F-00090_v1_classification_form.png`
- `ai-dev/active/F-00090/evidences/post/F-00090_v2_quality_kpis_section.png`
- `ai-dev/active/F-00090/evidences/post/F-00090_v3_regression_badge.png`
- `ai-dev/active/F-00090/evidences/post/F-00090_v4_empty_state.png`
- `ai-dev/active/F-00090/evidences/post/F-00090_v5_no_regressions.png`

## No regressions observed (functional)

- Throughput/Quality KPI block still renders on project dashboard.
- Incident detail page sections still render (status/metadata, design tabs, step pipeline, regression classification form).
- History rows without linked regressions show no regression badge.

Overall result: **FAIL** (V5 console error criterion not satisfied).


## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S16` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00090/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00090/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
