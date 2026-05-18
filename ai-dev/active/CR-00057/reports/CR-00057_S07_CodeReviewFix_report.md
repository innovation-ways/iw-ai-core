# CR-00057 — S07 Code Review Fix Report

## What was done

Addressed the S06 mandatory findings and the medium best-effort item:

1. **HIGH (resolved)** — `dashboard/static/chat_assistant/chat.js`
   - Fixed session creation so `directory` is no longer populated with `project_id`.
   - `chat.js` now resolves a trusted server-provided project directory from `GET /api/chat/config?project_id=...` and sends that value as `directory` when creating sessions.
   - Added lightweight per-project caching in the frontend to avoid repeated config fetches per project context.

2. **MEDIUM (resolved)** — `dashboard/routers/chat.py`
   - Added an INFO log in the no-`project_id` fail-open branch.
   - Included `project_directory` in chat config responses so frontend can pass repo root path to session creation without using opaque project IDs.

## Files changed

- `dashboard/static/chat_assistant/chat.js`
- `dashboard/routers/chat.py`

## Test results

- `uv run pytest tests/dashboard/test_chat_router.py -v --no-cov` ✅ (44 passed)

Note: running the same test command without `--no-cov` fails only due the repository-wide coverage threshold, not functional regressions.

## Pre-flight gates

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Issues / observations

- No blockers encountered.
