# F-00091 — S08 Tests Report

## What was done
- Added cross-project integration coverage for chat tabs and project listing:
  - `tests/integration/test_chat_panel_project_decoupling.py`
- Added Pi context-pct payload integration coverage across status branches:
  - `tests/integration/test_chat_tabs_context_pct_payload.py`
- Added dashboard smoke coverage for panel HTML + chat.js contract:
  - `tests/dashboard/test_chat_panel_html_smoke.py`

## Files changed
- `tests/integration/test_chat_panel_project_decoupling.py`
- `tests/integration/test_chat_tabs_context_pct_payload.py`
- `tests/dashboard/test_chat_panel_html_smoke.py`

## Boundary Behavior coverage check
- First-ever load on project page (URL seed): covered by JS guard assertions in `test_chat_panel_html_smoke.py` (`_seedAssistantProjectId` path + fallback), plus prior S02 tests.
- First-ever load on non-project page (fallback first project): covered by JS fallback assertion (`_setAssistantProjectId(projects[0].id)`) + S01 ordering test.
- Selected project no longer exists: covered by JS stale-selection reset path assertions in `test_chat_panel_html_smoke.py`.
- `/api/chat/projects` empty list: covered by existing `tests/dashboard/test_api_chat_projects.py::test_lists_empty_when_no_enabled_projects` and JS empty-state text assertion (`No projects available`).
- Active-tab pointer stale: covered by S03 tests and JS stale-key removal logic in existing `tests/dashboard/test_active_tab_restoration.py`.
- `localStorage` unavailable: covered by JS `try/catch` guard assertions (`ignore localStorage failures (private mode/quota)`) in `test_chat_panel_html_smoke.py`.
- Pi tab unknown window: covered by `test_get_tab_context_pct_unknown_window_for_pi_runtime`.
- OpenCode unhealthy unknown runtime: covered by prior S06 payload tests and backend/unit status tests (`tests/dashboard/test_chat_tabs_status_payload.py`, `tests/unit/test_context_usage_status.py`).
- Stream events during project switch: **covered by S19 browser verification scope** (not unit/integration automated here).
- New project registered mid-session/lazy refresh: covered by JS lazy refresh hook assertion (`_loadAssistantProjects`) in `test_chat_panel_html_smoke.py`.

## Test results
- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅
- `uv run pytest tests/integration/test_chat_panel_project_decoupling.py tests/integration/test_chat_tabs_context_pct_payload.py tests/dashboard/test_chat_panel_html_smoke.py -v`
  - **5 passed, 1 xfailed, 0 failed**

## Issues / observations
- The Pi `unknown_runtime` branch requested as a 200 payload currently returns HTTP 503 in `GET /api/chat/tabs/{id}` when `pi_runtime.health() == False` (early return in router). Added an `xfail` regression test documenting the intended contract and current behavior gap.
