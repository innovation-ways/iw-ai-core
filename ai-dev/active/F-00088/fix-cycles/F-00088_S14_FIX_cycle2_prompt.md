# F-00088 S14 Browser Verification Fix Cycle 2/5

The end-to-end browser verification for step S14 of work item F-00088 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  tests/e2e/**
  pyproject.toml
  uv.lock
  Makefile
  scripts/e2e_seed.py
  .github/workflows/e2e.yml
  docs/IW_AI_Core_Testing_Strategy.md
  skills/iw-ai-core-testing/**
  .claude/skills/iw-ai-core-testing/**
  ai-dev/work/TESTS_ENHANCEMENT.md

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00088/ai-dev/active/F-00088/F-00088_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# Browser Verification Report — F-00088-S14

**Work Item**: F-00088 — Structured Dashboard E2E Test Layer
**Step**: S14 — Browser Verification
**Agent**: qv-browser
**Base URL**: `http://localhost:9927`
**Date**: 2026-05-23

---

## Summary

| ID | Verification | Status | Failure Class | Notes |
|----|---|---|---|---|
| V0 | Pre-flight page sanity | **PASS** | — | No dangling fragment references found across 5 key pages |
| V1 | Journey 1 — Home → Project navigation | **PASS** | — | test_journey_home_navigation PASSED; project page renders |
| V2 | Journey 2 — Queue-to-merge happy path | **PASS** | — | test_journey_queue_to_merge PASSED; Queue page renders 2 approved items |
| V3 | Journey 3 — Code Q&A SSE stream | **PASS** | — | test_journey_code_qa_sse PASSED; Code page renders module list + chat panel |
| V4 | Journey 4 — Docs HTML + PDF export | **PASS** | — | test_journey_docs_export PASSED; Docs page shows 4 documents with Export buttons |
| V5 | Journey 5 — Jobs page multi-select filters | **PASS** | — | test_journey_jobs_filters PASSED; Jobs page renders 3 items with Filter button |
| V6 | Journey 6 — htmx fragments browser runtime | **FAIL** | `code_defect` | test_journey_htmx_fragments FAILED; snapshot unchanged after clicking Cancel |
| V7 | No Regressions | **PASS** | — | e2e_smoke: 2/2 pass; collect-only shows only unit tests; adjacent pages render |

**Overall Status**: `fail`
**Overall Failure Class**: `code_defect`

---

## V6 Failure Detail — `test_journey_htmx_fragments`

### What was tested
The journey opens the Queue page, finds the first non-skipped button (a "Cancel" button in the approved items table), clicks it (expecting an HTMX swap that changes the DOM), then asserts `snap_after != snap_before`.

### Failure
```
assert snap_after != snap_before, (
    "Expected HTMX swap to change the DOM. "
    "If this is inverted to assert snap_after == snap_before, "
    "the test would fail whenever HTMX updates work correctly."
)
AssertionError: Expected HTMX swap to change the DOM.
```
The full accessibility snapshot is **identical** before and after clicking the Cancel button.

### Root cause analysis

The test's `_find_htmx_filter_control()` finds `button "Cancel" [ref=e107]` from the Queue page's approved-items table row. That button triggers:

```html
hx-get="/project/iw-ai-core/api/confirm-item/cancel/CR-E2E-SEED"
hx-target="#confirm-dialog"
hx-swap="innerHTML"
```

This should inject a confirmation-dialog fragment into `#confirm-dialog`, which is present in `base.html` at `<div id="confirm-dialog"></div>`. The accessibility tree should show different `#confirm-dialog` content after the click — but it doesn't.

The snapshot being completely identical suggests the HTMX request either:
1. Returns an empty or no-op response (e.g., a 404 that htmx doesn't swap on, or a response without the expected fragment)
2. The confirm-dialog injection works but the accessibility tree format doesn't surface the `#confirm-dialog` innerHTML change

**This is a code defect**: the HTMX interaction on the Queue page's Cancel button is not producing a visible DOM change detectable by the accessibility snapshot.

### Evidence captured
- V6 spot-navigation screenshot: `ai-dev/active/F-00088/evidences/post/F-00088_v6_htmx_journey.png` (Jobs page; no console errors)
- Console logs: no `.playwright-cli/console-*.log` files written, confirming no browser JS exceptions

---

## V0 — Pre-flight Page Sanity

All fragment references across 5 key pages resolve to defined `id` attributes in the same response. No dangling `hx-target`, `hx-include`, `aria-controls`, or `href="#"` references detected.

| Page | htmx references checked | status |
|---|---|---|
| `/project/iw-ai-core/` | `hx-target="#global-search-results"` | defined |
| `/project/iw-ai-core/queue` | `hx-target="#confirm-dialog"` (x2) | defined |
| `/project/iw-ai-core/jobs` | `hx-target="#global-search-results"` | defined |
| `/project/iw-ai-core/code` | `hx-target="#code-status-panel"` | defined on that page |
| `/project/iw-ai-core/docs` | `hx-target="#docs-grid"`, `hx-include="#docs-filter-form"` etc. | defined |

---

## V7 — No Regressions

### e2e_smoke suite
```
uv run pytest tests/e2e/ -m e2e_smoke -v --no-cov
-> test_journey_home_navigation PASSED
-> test_journey_queue_to_merge PASSED
2 passed, 20 deselected
```

### collect-only check
```
uv run pytest tests/e2e/ --collect-only -q
-> 16 items collected (all harness self-check unit tests; 0 e2e-marked tests present)
Confirmed: e2e markers don't bleed into default collection
```

### Adjacent pages spot-checked
| Page | HTTP | Content visible | Console errors |
|---|---|---|---|
| `/project/iw-ai-core/` | 200 | Project card (Batches 0, Queue 2, Items 6) | None |
| `/project/iw-ai-core/batches` | 200 | Batches table with status filter links | None |
| `/project/iw-ai-core/history` | 200 | History list | None |
| `/project/iw-ai-core/docs` | 200 | 4 documents with Export buttons | None |
| `/project/iw-ai-core/tests` | 200 | Test runs page | None |
| `/project/iw-ai-core/code` | 200 | Module list + chat panel | None |

---

## Screenshots Captured

| Filename | Description |
|---|---|
| `F-00088_v1_home_navigation_journey.png` | V1 - Project home page (project card with nav tabs) |
| `F-00088_v2_queue_journey.png` | V2 - Queue page (2 approved items, Cancel buttons) |
| `F-00088_v3_code_qa_journey.png` | V3 - Code page (module list + collapsed chat panel) |
| `F-00088_v4_docs_export_journey.png` | V4 - Docs page (4 documents, Export links) |
| `F-00088_v5_jobs_filters_journey.png` | V5 - Jobs page (3 items, Filter button) |
| `F-00088_v6_htmx_journey.png` | V6 - Jobs page (htmx-heavy; no console errors) |
| `F-00088_v7_no_regressions.png` | V7 - History page (adjacent page spot-check) |

---

## Verdict

V1-V5 and V7 all pass. V6 fails with a `code_defect` - the HTMX Cancel button interaction on the Queue page does not produce a DOM change detectable by the accessibility snapshot. The fix-cycle agent should investigate:

1. Whether the `/api/confirm-item/cancel/{id}` endpoint returns the expected fragment
2. Whether the `#confirm-dialog` innerHTML is actually changing in the browser's live DOM
3. Whether the test's `_find_htmx_filter_control()` logic should be replaced with a more targeted HTMX trigger (e.g., the jobs page Filter button, which uses `multi_select` with real HTMX table refresh)

---

## JSON Result

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "F-00088",
  "overall_status": "fail",
  "overall_failure_class": "code_defect",
  "base_url_used": "http://localhost:9927",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass", "failure_class": null, "screenshot": "", "notes": "No dangling fragment references across 5 pages"},
    {"id": "V1", "name": "Journey 1 -- dashboard home -> project -> cross-tab navigation", "status": "pass", "failure_class": null, "screenshot": "F-00088_v1_home_navigation_journey.png", "notes": "test PASSED; project page renders"},
    {"id": "V2", "name": "Journey 2 -- queue-to-merge happy path", "status": "pass", "failure_class": null, "screenshot": "F-00088_v2_queue_journey.png", "notes": "test PASSED; Queue page renders 2 approved items"},
    {"id": "V3", "name": "Journey 3 -- Code Q&A SSE stream", "status": "pass", "failure_class": null, "screenshot": "F-00088_v3_code_qa_journey.png", "notes": "test PASSED; Code page renders module list + chat panel"},
    {"id": "V4", "name": "Journey 4 -- Docs HTML + PDF export", "status": "pass", "failure_class": null, "screenshot": "F-00088_v4_docs_export_journey.png", "notes": "test PASSED; 4 documents with Export buttons visible"},
    {"id": "V5", "name": "Journey 5 -- Jobs page multi-select filters", "status": "pass", "failure_class": null, "screenshot": "F-00088_v5_jobs_filters_journey.png", "notes": "test PASSED; Jobs page renders 3 items with Filter button"},
    {"id": "V6", "name": "Journey 6 -- htmx f

...(report truncated for prompt length)...

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S14` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00088/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00088/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
