# CR-00011 S03 Tests Report

## What Was Done

Implemented S03 (tests-impl) for CR-00011: wrote unit, template smoke, and integration tests for the project onboarding feature delivered in S01 (API) and S02 (Frontend).

## Files Changed

### New test files:

- **`tests/unit/test_project_onboarding.py`** — 39 tests for `dashboard/utils/project_onboarding.py` pure helpers
- **`tests/dashboard/test_project_onboarding_templates.py`** — 19 template smoke tests for `new_project_modal.html` and `directory_browser.html`
- **`tests/integration/test_project_onboarding_api.py`** — 26 integration tests for `/api/projects/*` routes

### Test categories:

| File | Tests | What it covers |
|------|-------|----------------|
| `test_project_onboarding.py` | 39 unit | `slugify_project_id`, `next_available_project_id`, `is_valid_project_id`, `safe_resolve_path`, `validate_repo_root` |
| `test_project_onboarding_templates.py` | 19 smoke | Modal renders with all fields, errors, buttons; directory browser with breadcrumbs, entries, error states |
| `test_project_onboarding_api.py` | 26 integration | `/api/projects/new`, `/api/projects/slug`, `/api/projects/browse`, `/api/projects/create` route behavior |

## Test Results

```
84 passed, 1 warning in 6.93s
```

- **Unit tests**: 39 passed (`test_project_onboarding.py`)
- **Template smoke tests**: 19 passed (`test_project_onboarding_templates.py`)
- **Integration tests**: 26 passed (`test_project_onboarding_api.py`)

Warning (`SAWarning: transaction already deassociated`) is a pre-existing transaction teardown artifact unrelated to these tests.

## Key Test Design Decisions

- **Unit tests use `tmp_path`** for filesystem operations — no real files touched, no DB
- **Integration tests override `_browse_root`** via module patching to use `tmp_path` as safe root, ensuring all path validation works in the test environment
- **`select()` from SQLAlchemy** used (not `Project.__table__.select()`) to ensure proper ORM entity return types with `display_name` attribute
- **Tests verify actual behavior**: `init_project` creates a DB row and `HX-Redirect: /` header is returned on success; validation errors re-render the modal form with appropriate error messages

## Issues/Observations

- Two pre-existing test collection errors (`test_fix_summary_ingestion.py`, `test_item_report_cli.py`) in the repo are unrelated to CR-00011
- The `is_valid_project_id` regex allows trailing hyphens (`my-project-`) and double hyphens (`my--project`) per the underlying regex `^[a-z0-9][a-z0-9-]*$` — tests reflect actual behavior rather than correcting the implementation
- `validate_repo_root` doesn't distinguish between `.git` as file vs directory (both show `git_path.exists()` as True but `is_dir()` differs) — the current implementation only checks `exists()`, not that `.git` is a directory