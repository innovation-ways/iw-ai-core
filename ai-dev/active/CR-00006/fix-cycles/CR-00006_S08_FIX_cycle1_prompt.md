# CR-00006 S08 Fix Cycle 1/5

The code review for step S08 of work item CR-00006 found issues that must be fixed.

## Findings to Fix

CRITICAL: test_sse_generator_streams_tokens_live fails - buffering bug in dashboard/routers/code_qa.py not fixed (S01 incomplete). CRITICAL: test_jobs_api.py 5/7 tests 404 - dashboard/routers/jobs_ui.py not implemented (S03 not done). Tests correctly written; implementation missing/broken.

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
