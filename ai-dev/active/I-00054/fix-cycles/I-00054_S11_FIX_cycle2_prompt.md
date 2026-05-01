# I-00054 S11 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S11 of work item I-00054 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# I-00054 S11 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9940`
- **E2E user:** `dev@example.local`
- **Page tested:** `/system/coverage` (unauthenticated)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Expand — label changes to "click to collapse" | **pass** | `evidences/post/I-00054_v1_expand_label.png` | Initial state: "click to expand". After click: "click to collapse", file rows visible. |
| V2 | Collapse — label returns to "click to expand" | **fail** | `evidences/post/I-00054_v2_collapse_label.png` | Clicking the dashboard row while it reads "click to collapse" does NOT collapse it. Label stays "click to collapse", file detail rows remain visible. |
| V3 | Re-expand — toggle works a second time | **fail** | `evidences/post/I-00054_v3_re_expand.png` | Cannot test re-expand because collapse (V2) never worked. Row stays expanded. |
| V4 | No regressions — other rows independent | **fail** | `evidences/post/I-00054_v4_no_regressions.png` | Could not test — dashboard row cannot be collapsed to observe independence. Other rows (executor, orch) still show "click to expand". |
| V5 | No console errors | **pass** | `evidences/post/I-00054_v5_no_console_errors.png` | 15 pre-existing htmx console errors on coverage page, but no new errors introduced by the toggle interactions. System status page loaded cleanly after. |

## Console / Network Errors
- Coverage page (`/system/coverage`) shows 15 console errors on load — these are **pre-existing** htmx errors unrelated to the toggle fix.
- No new errors introduced during V1–V4 interactions.
- Adjacent page (`/system/status`) loaded without errors after the test sequence.

## Root Cause — V2/V3/V4 Failure

**Code defect — the collapse handler never fires due to htmx trigger guard.**

`dashboard/templates/pages/system/coverage.html` lines 78–80:
```html
hx-trigger="click[this.dataset.expanded!='true'], keydown[key=='Enter'][this.dataset.expanded!='true']"
```

The htmx trigger only fires when `data-expanded != 'true'` (i.e., only when collapsed). Once htmx sets `data-expanded='true'` after a successful swap, clicking the row again fires the native JavaScript click handler (lines 111–119), but htmx's trigger already blocked the click event from propagating. Therefore `row.dataset.expanded` stays `'true'` permanently — no way to collapse.

The JS click handler also has a guard (`if (row.dataset.expanded === 'true')`) but this is dead code — it can never be reached when the row is expanded, because htmx blocks the event before it fires.

The fix requires either:
1. Removing the htmx trigger guard (`this.dataset.expanded!='true'`) so the htmx request fires on every click, and letting the server return empty content on collapse, OR
2. Having the JS click handler call `htmx.trigger()` manually to bypass the htmx trigger guard, OR
3. A server-side endpoint that toggles and returns appropriate HTML (expand or empty) regardless of state.

## Screenshots Captured
- `ai-dev/active/I-00054/evidences/post/I-00054_v1_expand_label.png` — dashboard row expanded, label reads "click to collapse"
- `ai-dev/active/I-00054/evidences/post/I-00054_v2_collapse_label.png` — dashboard row clicked again while expanded, label still "click to collapse" (FAIL)
- `ai-dev/active/I-00054/evidences/post/I-00054_v3_re_expand.png` — row still expanded, label still "click to collapse" (FAIL)
- `ai-dev/active/I-00054/evidences/post/I-00054_v4_no_regressions.png` — row still expanded (FAIL)
- `ai-dev/active/I-00054/evidences/post/I-00054_v5_no_console_errors.png` — system status page loaded without errors

## No Regressions Observed
- V5 confirmed adjacent pages (`/system/status`) load cleanly.
- The htmx errors are pre-existing and not caused by the toggle implementation.
- The expand-from-collapse works correctly (V1 passed).
- Other rows (executor, orch) show "click to expand" throughout — they are not affected by the dashboard row's state.

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


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
