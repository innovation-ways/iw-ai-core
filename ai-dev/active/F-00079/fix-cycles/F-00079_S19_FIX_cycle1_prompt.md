# F-00079 S19 Browser Verification Fix Cycle 1/3

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
- Item used for testing: F-00055 (seeded with diff data via fixture)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Files tab reachable | FAIL | evidences/post/F-00079_v1_files_tab_initial.png | Tab renders with toolbar (+3 files counter), but diff tree fails to render due to JS error |
| V2 | Per-file diff renders | FAIL | — | `Diff2HtmlUI.create is not a function` — diff rendering blocked by JS error |
| V3 | Step toggle filters diff | FAIL | — | Cannot test — diff never renders |
| V4 | Filter narrows files | FAIL | — | Cannot test — diff never renders |
| V5 | Untracked sub-panel works | FAIL | — | Cannot test — requires in-progress item with live worktree |
| V6 | Untracked hidden on archived | PASS | evidences/post/F-00079_v6_archived_no_untracked.png | "Other worktree files" panel absent on archived item |
| V7 | PDF export downloads | FAIL | — | HTTP 500 Internal Server Error |
| V8 | /tab/artifacts is 404 | PASS | evidences/post/F-00079_v8_artifacts_removed.png | Returns 404 as expected |
| V9 | Dark mode sync | FAIL | evidences/post/F-00079_v9_dark_mode.png | Cannot verify — diff never renders to check color sync |
| V10 | No regressions | FAIL | — | Cannot fully verify due to earlier failures |

## Console / Network Errors

1. **Critical JS Error**: `Diff2HtmlUI.create is not a function` at `dashboard/static/files.js:134`
   - The code calls `Diff2HtmlUI.create(diffText, {...})` but the bundled diff2html library only exposes the class constructor `new Diff2HtmlUI(...)`, not a static `create` method
   - This blocks diff rendering entirely

2. **PDF Export Error**: HTTP 500 on `GET /project/iw-ai-core/item/F-00055/files/export.pdf?step=all`

3. **favicon.ico 404**: Non-critical, browser default

## Screenshots captured
- `ai-dev/active/F-00079/evidences/post/F-00079_v1_files_tab_initial.png`
- `ai-dev/active/F-00079/evidences/post/F-00079_v9_dark_mode.png`
- `ai-dev/active/F-00079/evidences/post/F-00079_v8_artifacts_removed.png`

## Root Cause

**Code Defect in `dashboard/static/files.js:134`**

The JavaScript code uses `Diff2HtmlUI.create(diffText, {...})` but the bundled diff2html library (at `dashboard/static/vendor/diff2html/diff2html-ui-slim.min.js`) only provides the class constructor, not a static `create` factory method.

The correct usage for the bundled library version is:
```javascript
const diff2htmlUi = new Diff2HtmlUI(diffText, options);
diff2htmlUi.draw();
diff2htmlUi.resumeRender();
```

Not:
```javascript
_diff2htmlUi = Diff2HtmlUI.create(diffText, {...});
```

**Impact**: V1–V5, V7, V9 all fail because they depend on the diff rendering, which throws an uncaught JavaScript exception before the Diff2HtmlUI can draw.

**V6 and V8 pass** because they don't depend on diff rendering:
- V6: Verified the "Other worktree files" panel is absent on archived items
- V8: Verified the legacy `/tab/artifacts` route returns 404

## E2E Fixture

Added fixture at `ai-dev/active/F-00079/e2e_fixtures/001_files_view_seed.py` to seed diff data onto F-00055 (since F-00079 doesn't exist in the production-seeded E2E DB). The fixture creates:
- Aggregate diff with 3 files on `work_items.diff_text`
- Step runs for S01 (backend-impl) and S02 (frontend-impl) with per-step diffs

## No Regressions Observed

V8 (`/tab/artifacts` → 404) confirms the Artifacts tab removal is working. The Overview, Reports, Evidences, and Logs tabs were not re-visited due to the early failure blocking the Files tab from rendering.

## Summary

The browser verification failed due to a **code defect**: `Diff2HtmlUI.create` does not exist in the bundled diff2html library. The fix requires updating `dashboard/static/files.js` to use `new Diff2HtmlUI(...)` instead of `Diff2HtmlUI.create(...)`, or updating the bundled library to a version that provides the static `create` method.

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
