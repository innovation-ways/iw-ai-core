# CR-00011 S01 Api Report

## What Was Done

Implemented S01 (Api-impl) for CR-00011: the HTTP surface for the "+ New Project" button feature.

### New Module: `dashboard/utils/project_onboarding.py`

Four pure helper functions (no DB/FastAPI imports):

| Function | Purpose |
|----------|---------|
| `slugify_project_id(name)` | Lowercase + replace non-`[a-z0-9]` with `-`, strip dashes |
| `next_available_project_id(base, existing_ids)` | Append `-2`, `-3`, … on collision |
| `safe_resolve_path(raw, safe_root)` | Expand `~`, resolve, enforce path inside safe_root |
| `validate_repo_root(path)` | Check path exists, is a dir, contains `.git` |
| `is_valid_project_id(project_id)` | Regex check `^[a-z0-9][a-z0-9-]*$` |

### Router Additions: `dashboard/routers/projects.py`

Four new routes placed after `nav_projects` and before `project_selector`:

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/projects/new` | GET | Returns modal fragment with empty form context |
| `/api/projects/browse` | GET | Directory browser with breadcrumbs + entries |
| `/api/projects/slug` | GET | Returns slugified basename as plain text |
| `/api/projects/create` | POST | Validates form, calls `init_project()`, returns modal with errors or `HX-Redirect: /` |

Also added two private helpers: `_browse_root()` (reads `IW_CORE_BROWSE_ROOT` or `Path.home()`) and `_list_directory()` (iterates a path, skips broken symlinks).

### Key Design Decisions

- **No `init_project()` duplication**: `create_project` only calls `init_project()`; all file/DB writes happen inside that function.
- **Fail-early validation**: `safe_resolve_path` and `validate_repo_root` run in sequence; all errors collected before any template render (per design spec).
- **Safe browse root**: defaults to `Path.home()`, overridable via `IW_CORE_BROWSE_ROOT` env var.
- **`HX-Redirect: /` on success**: htmx full-page reload after project creation (matches design rationale).

## Files Changed

- `dashboard/routers/projects.py` — added 4 routes + 2 private helpers + new imports
- `dashboard/utils/project_onboarding.py` — new module with 5 pure functions

## Test Results

- **Linting** (`ruff check dashboard/routers/projects.py dashboard/utils/project_onboarding.py`): All checks passed
- **Type checking** (`mypy dashboard/routers/projects.py dashboard/utils/project_onboarding.py`): No issues found
- **Helper function smoke test**: All 11 assertions passed (slugify, next_available, safe_resolve, validate_repo_root, is_valid_project_id)

No integration tests written in S01 (deferred to S03 per the plan).

## Issues/Observations

- Two pre-existing test collection errors in the repo (`test_fix_summary_ingestion.py`, `test_item_report_cli.py`) cause `make test-unit` to fail before collecting any new tests. These are pre-existing import errors unrelated to this CR's changes.
- The route order in `projects.py` places the new `/api/projects/*` routes after `nav_projects` and before `project_selector`, matching the design spec's requested ordering.
- Templates `fragments/new_project_modal.html` and `fragments/directory_browser.html` are referenced by the routes but not yet created — those are S02 (Frontend-impl) deliverables.
