# F-00039 S05 Fix Cycle 1/5

The code review for step S05 of work item F-00039 found issues that must be fixed.

## Findings to Fix

CRITICAL: Missing Alembic migrations for doc_section_guides table and section_guides_snapshot column. S01 report claimed migrations were created but they do not exist in orch/db/migrations/versions/. DocSectionGuide model is defined in models.py but has no corresponding migration, making the feature non-functional.

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
