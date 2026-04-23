# F-00061 S09 Fix Cycle 1/5

The code review for step S09 of work item F-00061 found issues that must be fixed.

## Findings to Fix

3 CRITICAL issues: (1) executor/scope_gate.py logic modified violating Invariant 8 and Out-of-Scope; (2) 3 files need ruff format; (3) migration mypy error sa.JSONB not recognized

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
