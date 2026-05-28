# F-00091 S03 Frontend Report

## Summary
Implemented per-project active-tab persistence in `dashboard/static/chat_assistant/chat.js`.

### What changed
- Added `_activeTabKey(projectId)` returning `iw-chat-active-tab:<projectId>`.
- Migrated active-tab storage reads/writes from sessionStorage browser-tab keying to project-namespaced localStorage keying.
- Wrapped all new localStorage read/write/remove operations in `try/catch`.
- Updated `_bootstrapTabs()` (main and retry paths) to:
  - read namespaced active-tab pointer,
  - restore it only if it matches returned tabs,
  - fall back to `_tabs[0]` when missing/stale,
  - remove stale localStorage pointer when unmatched.
- Removed now-unused `_browserTabId` block and legacy active-tab key usage.
- Kept project-switch behavior resetting `_activeTabId = null` before `_bootstrapTabs()`.

## Files changed
- `dashboard/static/chat_assistant/chat.js`
- `tests/dashboard/test_active_tab_restoration.py`

## TDD
- RED: `uv run pytest tests/dashboard/test_active_tab_restoration.py -v`
  - `test_namespaced_active_tab_key_shape` failed (missing `_activeTabKey` helper).
  - `test_no_legacy_browser_tab_active_tab_storage_key_usage` failed (legacy `iw-chat-active-tab-<browserTabId>` usage still present).
- GREEN: after implementation, same test file passed (`2 passed, 0 failed`).

## Quality gates
- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Notes
- No backward migration for old sessionStorage keys was added by design. Existing `iw-chat-active-tab-<browserTabId>` entries are ignored after this change; users fall back to `_tabs[0]` once, then the new localStorage per-project key is established.
