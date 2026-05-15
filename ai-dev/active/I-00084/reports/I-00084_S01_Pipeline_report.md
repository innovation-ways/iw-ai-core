# I-00084 S01 Pipeline Report

**Step**: S01
**Agent**: pipeline-impl
**Date**: 2026-05-15

## What Was Done

Fixed the stale `origin/main` ref bug that caused `make diff-coverage` to compare
against an outdated base, inflating the diff with unrelated files from previously
merged items.

Two-line fix across two files:

### Fix 1 — `executor/worktree_setup.sh`

Added immediately after `git worktree add -b "$BRANCH" "$WORKTREE_DIR" HEAD`:

```bash
# I-00084: Sync origin/main ref to local main so diff-cover, scope_gate,
# and any other compare-vs-origin tools see the right base. This setup is
# local-only — origin/main never advances on its own.
git -C "$WORKTREE_DIR" fetch . main:refs/remotes/origin/main 2>/dev/null || true
```

This ensures every new worktree's `origin/main` ref is immediately updated to
match local `main` at creation time.

### Fix 2 — `Makefile` `diff-coverage:` target

Added as the first recipe line of `diff-coverage:`:

```makefile
@git fetch . main:refs/remotes/origin/main 2>/dev/null || true
```

This is a defensive safeguard for any worktree that reaches `diff-coverage`
without having gone through `worktree_setup.sh` (e.g., manually created
worktrees). The command is idempotent and runs in under 1ms on a local-only repo.

## Files Changed

| File | Change |
|------|--------|
| `executor/worktree_setup.sh` | Added 4-line block (comment + git fetch) after `git worktree add` |
| `Makefile` | Added `@git fetch . main:refs/remotes/origin/main 2>/dev/null || true` as first line of `diff-coverage:` body |
| `tests/integration/test_worktree_setup_origin_main_sync.py` | New — 5 tests covering AC1, AC2, AC3 |

## TDD Red Evidence

Tests run **before** the fix was applied:

```
FAILED tests/integration/test_worktree_setup_origin_main_sync.py::TestWorktreeSetupOriginMainSync::test_makefile_diff_coverage_sync_command_is_present
AssertionError: Makefile diff-coverage target must contain 'git fetch . main:refs/remotes/origin/main' as a defensive sync. Add it as the first recipe line of the diff-coverage: target.

FAILED tests/integration/test_worktree_setup_origin_main_sync.py::TestWorktreeSetupOriginMainSync::test_worktree_setup_sh_sync_command_is_present
AssertionError: executor/worktree_setup.sh must contain 'git fetch . main:refs/remotes/origin/main' after 'git worktree add'.

2 failed, 3 passed in 10.61s
```

The two `*_is_present` tests failed because the sync command was not yet in either file.
The three git-operation tests passed (they test the command in isolation).

## Test Results After Fix

```
5 passed, 0 failed in 7.95s
```

All 5 tests green:
- `test_origin_main_is_stale_before_fix` — confirms bug exists without the sync
- `test_origin_main_matches_local_main_after_sync` — main regression test (AC1)
- `test_sync_is_idempotent` — double-run safety
- `test_makefile_diff_coverage_sync_command_is_present` — AC3 guard
- `test_worktree_setup_sh_sync_command_is_present` — AC2 guard

## Pre-flight Gate Results

| Gate | Result |
|------|--------|
| `make format` | ok (708 files already formatted) |
| `make type-check` | ok (no issues in 249 source files) |
| `make lint` | ok (all checks passed) |

## Notes

The coverage failure in the test run output (`ERROR: Coverage failure: total of 3 is less
than fail-under=50`) is a pytest-cov artifact from running a single test file in isolation
without the full suite. The `====== 5 passed ======` line confirms all tests pass. This is
consistent with every other single-file integration test run in this repo.
