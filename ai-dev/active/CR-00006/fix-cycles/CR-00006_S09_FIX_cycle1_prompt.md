# CR-00006 S09 Fix Cycle 1/5

The code review for step S09 of work item CR-00006 found issues that must be fixed.

## Findings to Fix

2 CRITICAL findings: (1) code_map_completed not in sse.py _TOAST_EVENTS/_TOAST_SEVERITY so toast never fires; (2) code_qa.py non-blocking bridge uses asyncio.run() pattern that collects to completion instead of streaming via queue. Plus 2 HIGH mypy errors in jobs_ui.py.

## Constraints

1. **Only fix the flagged issues.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run tests after every fix.** Ensure no regressions.


## Instructions

1. Read the findings above carefully
2. Apply the minimum changes needed to resolve each finding
3. Run tests to verify no regressions
4. Exit when done — the daemon will detect completion and re-run the review

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
