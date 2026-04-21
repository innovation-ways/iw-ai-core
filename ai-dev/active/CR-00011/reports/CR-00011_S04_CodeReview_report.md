# CR-00011 S04 Code Review Report

## What Was Done

Reviewed CR-00011 S01-S03 implementation (project onboarding feature: API routes, frontend templates, tests).

## Files Reviewed

### Source files:
- `dashboard/utils/project_onboarding.py` — pure helpers (slugify, path validation, repo root validation)
- `dashboard/routers/projects.py` — FastAPI route handlers for `/api/projects/*`
- `dashboard/templates/fragments/new_project_modal.html` — new-project modal form fragment
- `dashboard/templates/fragments/directory_browser.html` — directory browser fragment

### Test files:
- `tests/unit/test_project_onboarding.py` — 39 unit tests
- `tests/dashboard/test_project_onboarding_templates.py` — 19 template smoke tests
- `tests/integration/test_project_onboarding_api.py` — 26 integration tests

## Test Results

```
Unit + template tests:   58 passed in 0.08s
Integration tests:       26 passed in 8.14s (1 pre-existing SAWarning)
Total:                   84 passed, 1 warning
```

## Code Review Findings

### No Critical Issues

### Minor Issues (not blocking — informational only):
1. **`validate_repo_root` doesn't check `.git` is a directory**: `git_path.exists()` is True for both file and directory `.git` entries; `is_dir()` check could distinguish them but current behavior (accepting .git file) is harmless since real repos have directories.
2. **`is_valid_project_id` allows trailing/double hyphens**: regex `^[a-z0-9][a-z0-9-]*$` permits `my-project-` and `my--project`. Tests reflect actual behavior. Could tighten but not a bug.
3. **ruff import-order warnings**: test files have unsorted imports — fixable with `ruff --fix` but non-blocking.

### Test Design Notes:
- `safe_resolve_path` correctly prevents path traversal via `relative_to()`
- `init_project` + `db.commit()` on success with `HX-Redirect: /` header — correct htmx redirect pattern
- Integration tests use module-level patching of `_browse_root` — correct approach for path validation in test environment
- `select()` from SQLAlchemy (not `Project.__table__.select()`) — correct ORM return type with `display_name` attribute

## Conclusion

All S01-S03 implementation is sound. Tests pass. No functional issues found. Minor ruff warnings in test files are cosmetic and do not affect correctness.