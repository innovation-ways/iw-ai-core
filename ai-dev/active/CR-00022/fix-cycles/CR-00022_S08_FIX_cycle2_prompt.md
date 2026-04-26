# CR-00022 S08 Fix Cycle 2/5

The code review for step S08 of work item CR-00022 found issues that must be fixed.

## Findings to Fix

Recipe-vs-flag consistency mismatch: 6 recipes (OSS-CA-01, OSS-CA-02, OSS-CI-06, OSS-CI-07, OSS-CI-08, OSS-CI-09) registered but not declared auto_apply_safe=True in Finding() constructors; 3 checks (OSS-DEP-06, OSS-TM-01, OSS-TM-08) declared auto_apply_safe=True but have no recipe

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
