# I-00040 S07 Fix Cycle 2/5

The code review for step S07 of work item I-00040 found issues that must be fixed.

## Findings to Fix

2 blocking issues: (1) CRITICAL - bg-red-700 not in compiled styles.css, banner will be invisible in production; (2) HIGH - IW_CORE_AGENT_CONTEXT cannot override IW_CORE_SKIP_ALEMBIC_GUARD at daemon startup path (main.py:134). Both must be fixed before merge.

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
