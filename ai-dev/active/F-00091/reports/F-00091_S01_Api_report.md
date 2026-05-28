# F-00091 S01 (api-impl) Report

Implemented `GET /api/chat/projects` in `dashboard/routers/chat.py`.

## What was done
- Added TDD tests in `tests/dashboard/test_api_chat_projects.py`:
  - enabled-only filtering + alphabetical ordering by `display_name` (case-insensitive behavior via lower sort).
  - empty-list behavior (`200` with `{"projects": []}`).
- Added new endpoint `GET /api/chat/projects` on the existing chat router:
  - Uses `db: Session = Depends(get_db)`.
  - Filters `Project.enabled = true`.
  - Sorts by `lower(display_name)` ascending.
  - Returns JSON shape: `{"projects": [{"id": ..., "display_name": ...}]}`.
  - Includes docstring referencing F-00091 purpose.

## Files changed
- `dashboard/routers/chat.py`
- `tests/dashboard/test_api_chat_projects.py`

## TDD evidence
- RED: `tests/dashboard/test_api_chat_projects.py::test_lists_enabled_projects_alpha` failed with `assert response.status_code == 200, got 404`.
- GREEN: `uv run pytest tests/dashboard/test_api_chat_projects.py -v` → `2 passed`.

## Preflight
- `make format`: fixed (ran `ruff format` on touched files, then `make format` passed)
- `make typecheck`: ok
- `make lint`: fixed (ruff import sort on new test file), then passed

## Result contract
```json
{
  "step": "S01",
  "agent": "api-impl",
  "work_item": "F-00091",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/routers/chat.py",
    "tests/dashboard/test_api_chat_projects.py"
  ],
  "preflight": {
    "format": "fixed",
    "typecheck": "ok",
    "lint": "fixed"
  },
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_api_chat_projects.py::test_lists_enabled_projects_alpha — assert response.status_code == 200, got 404",
  "blockers": [],
  "notes": ""
}
```
