# CR-00006 S06 Fix Cycle 2/5

The code review for step S06 of work item CR-00006 found issues that must be fixed.

## Findings to Fix

CRITICAL: Uncommitted Python router files in worktree violate CR Design step assignments. dashboard/routers/jobs_ui.py (new, untracked - should be S03), dashboard/routers/code_qa.py (modified - should be S01), dashboard/routers/sse.py (modified - should be S01/S03), dashboard/app.py (modified to register jobs_ui - should be S03). Frontend templates (S05 scope) are correct and pass review. Python-layer needs to be committed from its intended step before proceeding.

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
