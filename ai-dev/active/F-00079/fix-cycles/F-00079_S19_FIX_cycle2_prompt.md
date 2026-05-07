# F-00079 S19 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S19 of work item F-00079 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00079/ai-dev/active/F-00079/F-00079_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# F-00079 S19 Browser Verification Report

## Environment
- Base URL used: http://localhost:9920
- E2E user: dev@example.local
- Item used for testing: F-00055 (seeded with diff data via fixture `001_files_view_seed.py`)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Files tab reachable | FAIL | evidences/post/F-00079_v1_files_tab_initial.png | Tab renders with toolbar (+3 files counter), but diff tree fails to render: "Diff render error: e.map is not a function" |
| V2 | Per-file diff renders | FAIL | — | Cannot test — diff rendering throws before any diff cards appear |
| V3 | Step toggle filters diff | FAIL | — | Cannot test — diff never renders |
| V4 | Filter narrows files | FAIL | — | Cannot test — diff never renders |
| V5 | Untracked sub-panel works | FAIL | — | F-00055 is archived (worktree_alive=false), so untracked panel is hidden by design — need an in-progress item to test V5 |
| V6 | Untracked hidden on archived | PASS | evidences/post/F-00079_v6_archived_no_untracked.png | "Other worktree files" panel absent on archived item F-00055 |
| V7 | PDF export downloads | FAIL | — | HTTP 500 Internal Server Error on GET /project/iw-ai-core/item/F-00055/files/export.pdf?step=all |
| V8 | /tab/artifacts is 404 | PASS | evidences/post/F-00079_v8_artifacts_removed.png | Returns HTTP 404 "Not Found" — Artifacts tab correctly removed |
| V9 | Dark mode sync | FAIL | — | Cannot verify — diff never renders to check color scheme sync |
| V10 | No regressions | FAIL | — | V8 passes (no regression in artifacts removal), but other tabs not fully tested due to V1 failure |

## Console / Network Errors

1. **Critical JS Error**: `TypeError: e.map is not a function` at `FileListRenderer.render` (in diff2html-ui-slim.min.js:1:49418)
   - Triggered when `new Diff2HtmlUI(diffText, {...})` is called with the full options object from `files.js:133`
   - The error occurs during HTML rendering inside the Diff2HtmlUI constructor itself
   - The `matching: "lines"` option may be causing an array to be expected but not received

2. **PDF Export Error**: HTTP 500 on `GET /project/iw-ai-core/item/F-00055/files/export.pdf?step=all`

3. **favicon.ico 404**: Non-critical, browser default

## Screenshots captured
- `ai-dev/active/F-00079/evidences/post/F-00079_v1_files_tab_initial.png`
- `ai-dev/active/F-00079/evidences/post/F-00079_v6_archived_no_untracked.png`
- `ai-dev/active/F-00079/evidences/post/F-00079_v8_artifacts_removed.png`

## Root Cause

**Code Defect in `dashboard/static/files.js`**

The diff2html bundle crashes during constructor initialization with `e.map is not a function` in `FileListRenderer.render`. This happens when `files.js` calls:
```javascript
_diff2htmlUi = new Diff2HtmlUI(diffText, {
  drawUnifiedDiff: true,
  colorScheme: _isDarkMode() ? "dark" : "light",
  fileContentToggle: false,
  fileTree: true,
  highlight: true,
  matching: "lines",        // ← likely culprit
  maxFragments: 0,
  renderMode: "replace",
  showFiles: true,
  smartPhone: false,
  synchronizedScroll: true,
  unifiedDiff: true,
});
```

The `matching: "lines"` option may expect an array but receives a string, causing `e.map is not a function` to fire during FileListRenderer initialization.

**Note**: The original report mentioned `Diff2HtmlUI.create is not a function` — this was incorrect. The code already uses `new Diff2HtmlUI(...)`, and the error is `e.map is not a function`, not `create is not a function`.

## E2E Fixture

Added fixture at `ai-dev/active/F-00079/e2e_fixtures/001_files_view_seed.py` to seed diff data onto F-00055:
- Aggregate diff with 3 files on `work_items.diff_text`
- Step runs for S01 (backend-impl) and S02 (frontend-impl) with per-step diffs
- F-00055 is marked archived (archived_at is set), so V5 cannot be tested on it

## No Regressions Observed

- V8 (`/tab/artifacts` → 404) confirms the Artifacts tab removal is working correctly
- The Overview, Reports, Evidences, and Logs tabs were not individually revisited due to the V1 failure blocking the Files tab from rendering fully

## Summary

Browser verification failed due to **code defects**:
1. `e.map is not a function` in `FileListRenderer.render` — diff2html UI fails to initialize, blocking V1–V4 and V9
2. HTTP 500 on PDF export endpoint, blocking V7

Passing verifications:
- V6: Untracked panel correctly hidden on archived items
- V8: Legacy `/tab/artifacts` route correctly returns 404

## Verifications requiring further investigation

- **V5**: Needs an in-progress (non-archived) item with a live worktree to verify the untracked sub-panel
- **V7**: PDF endpoint returns 500 — likely a missing dependency or template error

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "qv-browser",
  "work_item": "F-00079",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9920",
  "verifications": [
    {"id": "V1", "name": "Files tab reachable", "status": "fail", "screenshot": "evidences/post/F-00079_v1_files_tab_initial.png", "notes": "e.map is not a function in FileListRenderer.render"},
    {"id": "V2", "name": "Per-file diff renders", "status": "fail", "screenshot": "", "notes": "Cannot test — diff rendering throws"},
    {"id": "V3", "name": "Step toggle filters diff", "status": "fail", "screenshot": "", "notes": "Cannot test — diff never renders"},
    {"id": "V4", "name": "Filter narrows files", "status": "fail", "screenshot": "", "notes": "Cannot test — diff never renders"},
    {"id": "V5", "name": "Untracked sub-panel works", "status": "fail", "screenshot": "", "notes": "F-00055 is archived — need in-progress item"},
    {"id": "V6", "name": "Untracked hidden on archived", "status": "pass", "screenshot": "evidences/post/F-00079_v6_archived_no_untracked.png", "notes": "Panel correctly absent"},
    {"id": "V7", "name": "PDF export downloads", "status": "fail", "screenshot": "", "notes": "HTTP 500 Internal Server Error"},
    {"id": "V8", "name": "/tab/artifacts is 404", "status": "pass", "screenshot": "evidences/post/F-00079_v8_artifacts_removed.png", "notes": "Returns 404 as expected"},
    {"id": "V9", "name": "Dark mode sync", "status": "fail", "screenshot": "", "notes": "Cannot verify — diff never renders"},
    {"id": "V10", "name": "No regressions", "status": "fail", "screenshot": "", "notes": "V8 passes, others blocked by V1"}
  ],
  "console_errors_observed": [
    "TypeError: e.map is not a function at FileListRenderer.render (diff2html-ui-slim.min.js:1:49418)",
    "HTTP 500 on /project/iw-ai-core/item/F-00055/files/export.pdf?step=all",
    "favicon.ico 404 (non-critical)"
  ],
  "screenshots": [
    "evidences/post/F-00079_v1_files_tab_initial.png",
    "evidences/post/F-00079_v6_archived_no_untracked.png",
    "evidences/post/F-00079_v8_artifacts_removed.png"
  ],
  "notes": "V1 failure is a code defect in Diff2HtmlUI initialization. V5 requires a non-archived item with live worktree. V7 PDF export returns HTTP 500."
}
```

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S19` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00079/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00079/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
