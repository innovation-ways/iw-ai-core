# CR-00011 S05 Code Review Fix Report

## What Was Done

Fixed three minor issues identified in S04 Code Review:

1. **`validate_repo_root` now checks `.git` is a directory** (`dashboard/utils/project_onboarding.py:69`): Added `is_dir()` check to distinguish `.git` directory from `.git` file (e.g., git-worktree).

2. **`is_valid_project_id` now rejects trailing/double hyphens** (`dashboard/utils/project_onboarding.py:12`): Changed regex from `^[a-z0-9][a-z0-9-]*$` to `^[a-z0-9](-?[a-z0-9]+)*$` which prevents:
   - Trailing hyphens (e.g., `my-project-`)
   - Double hyphens (e.g., `my--project`)

3. **Fixed ruff import-order warning** in `tests/unit/test_project_onboarding.py`: Moved `Path` import to `TYPE_CHECKING` block.

## Files Changed

- `dashboard/utils/project_onboarding.py` — regex fix + `.git` is_dir check
- `tests/unit/test_project_onboarding.py` — updated 2 tests + moved Path to TYPE_CHECKING

## Test Results

```
Unit + template tests:   59 passed in 0.10s
Integration tests:       26 passed in 6.95s (1 pre-existing SAWarning)
Total:                   85 passed, 1 warning
```

## Issues/Observations

- Remaining ruff warnings in `test_project_onboarding_api.py` (TC003, S110, S108) were NOT mentioned in S04 findings — they are different from the import-order issue that was fixed.
- The S110 `try-except-pass` and S108 `/tmp` usage are intentional test patterns, not issues.
