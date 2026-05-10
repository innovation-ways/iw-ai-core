# I-00075 — S13 Browser Verification Report

**Work Item**: I-00075 — Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills
**Step**: S13 (qv-browser) — re-verification run after the `step_pipeline.html` duration-format fix landed.
**Base URL used**: `http://localhost:9939` (from `$IW_BROWSER_BASE_URL`)
**Result**: ✅ **PASS** — all of V0..V3 passed. `overall_failure_class = null`.

> The earlier S13 run failed because `dashboard/templates/components/step_pipeline.html`
> used a str.format-style duration template (`"{}m{}s"|format(...)`) with Jinja2's
> printf-style `format` filter, raising `TypeError: not all arguments converted during
> string formatting` and 500-ing `/item/I-99001` (the only item whose steps had a
> non-NULL `duration_secs`). The worktree now has the fix at `step_pipeline.html:24`
> (`"%dm%02ds"|format(...)` / `"%ds"|format(...)`), and this run re-verifies it end-to-end.
>
> Note: the E2E stack served the dashboard without an interactive login form — the root
> URL `/` resolved straight to the Projects page — so the provided
> `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD` credentials were not needed; no
> auth prompt was presented.

## Pass/Fail Table

| V | Name | Status | Failure class | Notes |
|---|------|--------|---------------|-------|
| V0 | Pre-flight page sanity | ✅ PASS | null | Fragment-reference scan on `/item/I-99001`, `/item/CR-00001`, `/history`, `/batches`: 0 dangling `hx-target` / `hx-include` / `aria-controls` / `aria-labelledby` / `href="#…"` / `for` references. Only console entry on every page is a benign `GET /favicon.ico 404` — no JS/HTMX load-time exceptions. All four routes returned HTTP 200. |
| V1 | Fix-cycle amber `↺S02` pills render on I-99001 | ✅ PASS | null | `/project/iw-ai-core/item/I-99001` → HTTP 200. See details below. |
| V2 | No regression — zero-cycle item renders cleanly | ✅ PASS | null | `CR-00001` (production pg_dump item): HTTP 200, Step Pipeline renders; **0** `iw-pipeline-pill--fixcycle`, **0** `iw-pipeline-connector--fixcycle`; "Fix Cycles" stat = 0; no new console errors. |
| V3 | No regressions — adjacent item-overview flows | ✅ PASS | null | `/batches` → HTTP 200, lists `BATCH-I00075DEMO`; `/history` → HTTP 200, lists `I-99001` alongside the pg_dump items `CR-00001`, `F-00055`, `I-00001`; no new console errors on any page visited. |

## V1 details — `/project/iw-ai-core/item/I-99001`

HTTP 200. The Step Pipeline macro (`dashboard/templates/components/step_pipeline.html:36-44`) rendered the fix-cycle branch as designed:

- `iw-pipeline-pill--fixcycle` elements: **2** ✓ — matches the fixture's deliberate 2-cycle count.
- `iw-pipeline-connector--fixcycle` elements: **2** ✓ — one immediately precedes each amber pill. Source order verified:
  `…pill--completed (S02)` → `connector--fixcycle` → `pill--fixcycle (cycle 1)` → `connector--fixcycle` → `pill--fixcycle (cycle 2)` → `connector` → `pill--completed (S03)`.
- Titles: `title="↺S02: fix cycle 1"` and `title="↺S02: fix cycle 2"` — both present ✓ (`step_pipeline.html:40`).
- Inner span: `<span class="iw-pipeline-pill-id">↺S02</span>` present **×2** ✓; the `↺` glyph (U+21BA) is visible in the accessibility snapshot (`↺S02` text under refs e112/e113 and e115/e116).
- Page header also shows the "Fix Cycles 2" summary button, and the StepRuns table row `S02 … ×3 … 2↻`, consistent with the fixture (3 StepRuns + 2 FixCycles on S02).
- Console: only `GET /favicon.ico 404` — no exceptions.

Screenshot: `evidences/post/I-00075_v1_fix_cycle_amber_pills.png`

## No regressions observed

**V2** — `/project/iw-ai-core/item/CR-00001` (item restored from the production `pg_dump`, `Fix Cycles = 0`): HTTP 200; the Step Pipeline section renders normally, contains **zero** `iw-pipeline-pill--fixcycle` and **zero** `iw-pipeline-connector--fixcycle` elements, the "Fix Cycles" stat reads `0`, and no new console errors appeared (favicon 404 only). The amber-pill branch is correctly suppressed when `fix_cycle_count == 0`, and — importantly — the previously-crashing duration-format line no longer breaks rendering even though CR-00001's `S00` step is `pending` (NULL duration → the `{% if step.duration_secs is not none %}` guard is false, as before; the fix is exercised positively by I-99001's zero-second-duration steps).

**V3** — Adjacent flows: the Batches list page (`/project/iw-ai-core/batches`) renders HTTP 200 and lists `BATCH-I00075DEMO`. The History page (`/project/iw-ai-core/history`) renders HTTP 200 and lists all four items — `CR-00001`, `F-00055`, `I-00001`, `I-99001` — so the synthetic demo item appears alongside the pg_dump-restored items. No new console errors were observed on `/batches`, `/history`, or any other page visited during V1..V3 (the only console entry anywhere is the static-asset `favicon.ico` 404, present identically on every page including pre-existing ones — not a regression).

## Screenshots captured

- `ai-dev/active/I-00075/evidences/post/I-00075_v1_fix_cycle_amber_pills.png`
- `ai-dev/active/I-00075/evidences/post/I-00075_v2_no_regression_zero_cycle_item.png`
- `ai-dev/active/I-00075/evidences/post/I-00075_v3_no_regressions.png`

(Stale screenshots from the prior failed S13 attempt — taken while the E2E stack was down — were removed from `evidences/post/` so the directory matches this passing run.)

## Issues found

None. No code defects, no environment data gaps, no spec mismatches.

- The fixture `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` was already applied by the daemon's fixture-apply hook before this verification ran; `I-99001` was present with the expected 3 WorkflowSteps (S01/S02/S03, all `completed`) and exactly 2 `FixCycle` rows on S02.
- The render branch under test (`dashboard/templates/components/step_pipeline.html:36-44`) was read-only for this step and was not modified.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00075",
  "overall_status": "pass",
  "overall_failure_class": null,
  "base_url_used": "http://localhost:9939",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass", "failure_class": null, "screenshot": "", "notes": "No dangling fragment refs on /item/I-99001, /item/CR-00001, /history, /batches; only console entry is favicon.ico 404."},
    {"id": "V1", "name": "Fix-cycle amber pills render on I-99001", "status": "pass", "failure_class": null, "screenshot": "I-00075_v1_fix_cycle_amber_pills.png", "notes": "HTTP 200; exactly 2 iw-pipeline-pill--fixcycle + 2 iw-pipeline-connector--fixcycle; titles '↺S02: fix cycle 1' and '↺S02: fix cycle 2'; ↺S02 span x2; 'Fix Cycles 2' header."},
    {"id": "V2", "name": "No regression on zero-cycle item", "status": "pass", "failure_class": null, "screenshot": "I-00075_v2_no_regression_zero_cycle_item.png", "notes": "CR-00001 HTTP 200; 0 fixcycle pills/connectors; Fix Cycles stat = 0; no new console errors."},
    {"id": "V3", "name": "No regressions on adjacent flows", "status": "pass", "failure_class": null, "screenshot": "I-00075_v3_no_regressions.png", "notes": "/batches HTTP 200 (lists BATCH-I00075DEMO); /history HTTP 200 (lists I-99001 + CR-00001 + F-00055 + I-00001); no new console errors."}
  ],
  "console_errors_observed": ["GET http://localhost:9939/favicon.ico 404 (benign, on every page)"],
  "screenshots": [
    "I-00075_v1_fix_cycle_amber_pills.png",
    "I-00075_v2_no_regression_zero_cycle_item.png",
    "I-00075_v3_no_regressions.png"
  ],
  "notes": "Re-verification after the step_pipeline.html duration-format fix (printf-style %dm%02ds). All Vs pass; the fix-cycle amber-pill render branch (step_pipeline.html:36-44) works end-to-end against the seeded I-99001 fixture."
}
```
