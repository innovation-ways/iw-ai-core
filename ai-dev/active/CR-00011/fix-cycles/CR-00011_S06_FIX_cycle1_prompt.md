# CR-00011 S06 Fix Cycle 1/5

The code review for step S06 of work item CR-00011 found issues that must be fixed.

## Findings to Fix

CRITICAL: + New Project button missing from project_selector.html and modal-root missing from base.html (S02 claimed to add them but git shows no changes). CRITICAL: ID pre-fill does not function — /api/projects/slug is never called from the modal. HIGH: Breadcrumb entries missing 'path' attribute causing navigateTo(undefined). S07 must fix these before QV gates can pass.

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
