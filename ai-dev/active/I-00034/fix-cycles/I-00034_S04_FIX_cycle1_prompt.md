# I-00034 S04 Fix Cycle 1/5

The code review for step S04 of work item I-00034 found issues that must be fixed.

## Findings to Fix

test_I00034_in_progress_step_returns_none_duration_and_aggregated_start currently FAILS (duration_secs=0.0 instead of None) against post-fix S01 code. AC3 requires in-progress steps to have duration_secs=None. This is the documented S01 gap but it means the test cannot serve its purpose as a regression guard. HIGH finding: fix _aggregate_step_spans to detect NULL completed_at and return None for in-progress steps.

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
