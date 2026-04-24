# I-00037 S06 Fix Cycle 1/5

The code review for step S06 of work item I-00037 found issues that must be fixed.

## Findings to Fix

6 findings: 2 CRITICAL (SIM222 assertion always-true makes HTTP smoke tests no-ops), 4 HIGH (lint: F401 unused import, W292 missing newline x2, N802 function name casing)

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
