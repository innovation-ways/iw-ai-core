# CR-00025 S04 Fix Cycle 1/5

The code review for step S04 of work item CR-00025 found issues that must be fixed.

## Findings to Fix

3 mandatory fixes: test_approve_oversize_keeps_status_draft_no_rows (CRITICAL — AC4 rollback not verified via CliRunner), test_unknown_extension_defaults_to_octet_stream (HIGH — platform-dependent MIME assertion), test_non_file_entries_ignored (HIGH — symlink creates file on this platform)

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
