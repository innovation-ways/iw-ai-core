# I-00054 S11 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S11 of work item I-00054 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# I-00054 S11 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9940` (from `$IW_BROWSER_BASE_URL`)
- **E2E user:** `dev@example.local`
- **Page tested:** `/system/coverage` (unauthenticated)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Expand — label changes to "click to collapse" | **pass** | `evidences/post/I-00054_v1_expand_label.png` | dashboard row clicked; label correctly changed from "click to expand" → "click to collapse"; file detail rows appeared below |
| V2 | Collapse — label returns to "click to expand" and detail rows disappear | **fail** | `evidences/post/I-00054_v2_collapse_label.png` | Clicking the same row a second time does NOT collapse. Label remains "click to collapse" and file detail rows remain visible |
| V3 | Re-expand — toggle works a second time | **fail** | `evidences/post/I-00054_v3_re_expand.png` | Same as V2 — collapse is broken so re-expand can't be tested from a collapsed state |
| V4 | No regressions — other rows are independent | **pass** | `evidences/post/I-00054_v4_no_regressions.png` | executor row expands independently to "click to collapse"; dashboard row retains its expanded state; orch row remains at "click to expand" — no cross-contamination |
| V5 | No console errors | **pass** | `evidences/post/I-00054_v5_no_console_errors.png` | Navigated to /system/status and back to /system/coverage; no JS errors in browser console |

## Console / Network Errors
None observed. No console error logs were produced during the session.

## No Regressions
- V4 confirms that expanding one row does not affect other rows' labels or state — each package row is independent.
- V5 confirms sidebar navigation works and the coverage page loads correctly after visiting other system pages.
- No JavaScript exceptions were raised during any interaction.

## Screenshots captured
- `ai-dev/active/I-00054/evidences/post/I-00054_v1_expand_label.png`
- `ai-dev/active/I-00054/evidences/post/I-00054_v2_collapse_label.png`
- `ai-dev/active/I-00054/evidences/post/I-00054_v3_re_expand.png`
- `ai-dev/active/I-00054/evidences/post/I-00054_v4_no_regressions.png`
- `ai-dev/active/I-00054/evidences/post/I-00054_v5_no_console_errors.png`

## Root Cause

**CODE DEFECT** — collapse toggle is broken.

The JavaScript in `dashboard/templates/pages/system/coverage.html` (lines 108–134) has a logic flaw in how it handles the expand/collapse cycle:

1. **Click handler** (lines 111–120) fires on every click. When `expanded === 'true'` (row is already expanded), it:
   - Clears `filesDiv.innerHTML` (visible removal)
   - Sets `row.dataset.expanded = 'false'`
   - Sets `label.textContent = 'click to expand'`
   - Calls `htmx.trigger(row, 'click')` — which re-fires the htmx GET request for the same `/system/coverage/files/{pkg}` endpoint

2. **htmx:afterSwap listener** (lines 123–133) fires after every htmx response targeting `#files-{pkg}`:
   - It unconditionally sets `row.dataset.expanded = 'true'` and `label.textContent = 'click to collapse'`

The conflict: the click handler pre-clears the UI and flips the label, but then the htmx swap (re-)triggers the afterSwap listener which overwrites the collapse state back to expanded. The GET response for an already-expanded row still contains file data, so the content reappears. Net result: click handler sets collapse, then afterSwap overrides it back to expand — no net change.

**Fix direction**: The `htmx:afterSwap` listener should only set `expanded=true` when the returned content is non-empty (i.e., an expand operation). For collapse, the click handler already clears the div and sets the label — the htmx trigger should be conditional (or the afterSwap should distinguish between an expand-response and a collapse-response). A simple guard: only update label/expanded in afterSwap if the response has actual file rows, or skip the htmx trigger on collapse entirely since the click handler already handles the UI state locally.

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/I-00054/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00054/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (3/3). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
