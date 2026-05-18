# CR-00057 — S03 Frontend Report

## What was done

- Updated `dashboard/static/chat_assistant/chat.js` to make model-config and session creation project-aware without changing templates.
- Added `_currentProjectId()` helper to parse project context from `window.location.pathname` using `^/project/([^/]+)/` semantics.
- Wired project context into chat config fetch:
  - Project pages now call `/api/chat/config?project_id=<id>`.
  - Non-project pages continue calling bare `/api/chat/config` (fail-open behavior).
- Wired project context into session creation:
  - `_createSession()` now sends `directory` when a project id is present.
  - Chosen wire format is **project_id sentinel** (not repo root path), consistent with step guidance to avoid unplanned API-scope expansion.
- Added `_lastProjectId` tracking and refresh behavior for SPA-like navigation:
  - On each 30s model refresh tick, compares current project id to last fetched id.
  - If changed, clears the model dropdown and re-fetches project-scoped config.

## Files changed

- `dashboard/static/chat_assistant/chat.js`

## Test / quality results

- `make format` ✅
- `make lint` ✅
- `node --check dashboard/static/chat_assistant/chat.js` ✅
- `make typecheck` ✅

Behavioral automation for this static JS path is deferred as planned:

- `test_summary`: n/a — covered by S04 + S15
- `tdd_red_evidence`: n/a — frontend JS in a no-build static asset; behavior covered by S04 dashboard tests and S15 qv-browser

## Issues / observations

- No blocker encountered.
- `directory` is sent as project id sentinel intentionally. If backend runtime later requires absolute `repo_root`, that should be handled server-side (API/backend step), not by expanding frontend scope.
