# I-00075 S13 QvBrowser Report

> Full detail: `ai-dev/active/I-00075/reports/I-00075_S13_BrowserVerification_Report.md`

**Result:** ✅ PASS — all of V0..V3 passed. `overall_failure_class = null`.
**Base URL:** `http://localhost:9939` (`$IW_BROWSER_BASE_URL`)

## What was done

Re-ran the browser verification for the fix-cycle amber-pill render branch after the
`step_pipeline.html` duration-format fix landed (printf-style `"%dm%02ds"|format(...)`
replacing the broken `"{}m{}s"|format(...)`).

- **V0** — Pre-flight: visited `/item/I-99001`, `/item/CR-00001`, `/history`, `/batches`;
  all HTTP 200; no dangling `hx-target`/`hx-include`/`aria-controls`/`aria-labelledby`/`href="#…"`/`for`
  references; only console entry anywhere is the benign `GET /favicon.ico 404`.
- **V1** — `/project/iw-ai-core/item/I-99001` renders HTTP 200 with exactly **2**
  `iw-pipeline-pill--fixcycle` divs (titles `↺S02: fix cycle 1` / `↺S02: fix cycle 2`),
  each preceded by an `iw-pipeline-connector--fixcycle`, each with an inner
  `<span class="iw-pipeline-pill-id">↺S02</span>`. Header shows "Fix Cycles 2";
  StepRuns table shows S02 ×3 / 2↻ — consistent with the fixture.
- **V2** — `/project/iw-ai-core/item/CR-00001` (pg_dump item, Fix Cycles = 0) renders
  cleanly: **0** `iw-pipeline-pill--fixcycle`, **0** `iw-pipeline-connector--fixcycle`,
  no new console errors.
- **V3** — `/batches` lists `BATCH-I00075DEMO`; `/history` lists `I-99001` alongside the
  production pg_dump items (`CR-00001`, `F-00055`, `I-00001`); no new console errors.

## Files changed

None. Read-only verification step. (Stale screenshots from the prior failed S13 attempt
were removed from `evidences/post/`.)

## Test results

N/A — browser verification only. All declared verifications pass.

## Issues / observations

None. No code defects, no environment data gaps, no spec mismatches. The fixture
`ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` had already been applied by
the daemon's fixture-apply hook; `I-99001` was present with 3 WorkflowSteps and 2
FixCycle rows on S02 as designed. The previously-reported `TypeError: not all arguments
converted during string formatting` on `/item/I-99001` is resolved by the fix at
`dashboard/templates/components/step_pipeline.html:24`.

## Screenshots

- `ai-dev/active/I-00075/evidences/post/I-00075_v1_fix_cycle_amber_pills.png`
- `ai-dev/active/I-00075/evidences/post/I-00075_v2_no_regression_zero_cycle_item.png`
- `ai-dev/active/I-00075/evidences/post/I-00075_v3_no_regressions.png`
