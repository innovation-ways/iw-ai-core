# F-00091 S02 Frontend Report

## What was done
- Updated `dashboard/templates/chat_assistant/panel.html` header to add the project `<select id="chat-assistant-project-select">` with initial `Loading…` option.
- Kept `#chat-assistant-title` as a visually-hidden span for compatibility.
- Added collapsed-state CSS selector in the template so project select is hidden when collapsed.
- Updated `dashboard/static/chat_assistant/chat.js` to:
  - Remove `_currentProjectId` entirely.
  - Add `_assistantProjectId()`, `_setAssistantProjectId(projectId)`, `_seedAssistantProjectId()`, `_loadAssistantProjects()`.
  - Add project list/select rendering + empty-project handling.
  - Add lazy initialization chain (`_loadAssistantProjects -> _seedAssistantProjectId -> _bootstrapTabs`) when panel opens.
  - Replace all former `_currentProjectId()` call sites with `_assistantProjectId()`.
  - Wire project dropdown change to persist selection, tear down old tab streams, and re-bootstrap tabs without page reload.
- Appended selector styles to `dashboard/static/chat_assistant/chat.css`.
- Added `tests/dashboard/test_assistant_project_decoupling.py` covering:
  - Project selector existence + initial option structure in served HTML.
  - No `_currentProjectId` reference in served `chat.js`.

## TDD
- RED evidence:
  - `tests/dashboard/test_assistant_project_decoupling.py::test_dropdown_renders`
  - `AssertionError: assert None is not None` (selector missing before implementation)
- GREEN after implementation:
  - `2 passed, 0 failed`

## Files changed
- `dashboard/templates/chat_assistant/panel.html`
- `dashboard/static/chat_assistant/chat.js`
- `dashboard/static/chat_assistant/chat.css`
- `tests/dashboard/test_assistant_project_decoupling.py`

## Quality gates / tests run
- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅
- `uv run pytest tests/dashboard/test_assistant_project_decoupling.py -v` ✅

## Notes
- Kept behavior within S02 scope (no S03 active-tab key migration, no S07 progress bar work).
