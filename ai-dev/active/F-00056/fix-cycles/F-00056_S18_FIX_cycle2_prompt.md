# F-00056 S18 Browser Verification Fix Cycle 2/2

The end-to-end browser verification for step S18 of work item F-00056 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

FAIL: Execution report routes/tab missing in dashboard/routers/items.py (S05 api-impl not completed); tab button missing in item_detail.html (S07 frontend-impl not completed); standalone page template missing. Report: ai-dev/active/F-00056/reports/F-00056_S18_BrowserVerification_Report.md

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/F-00056/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (2/2). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
