# CR-00064 S01 API Report

## Step Summary

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant  
**Step**: S01 — API endpoint: `POST /api/chat/tabs/{tab_id}/clear`  
**Agent**: api-impl  
**Status**: ✅ Complete

---

## What Was Done

Implemented the `POST /api/chat/tabs/{tab_id}/clear` endpoint in `dashboard/routers/chat.py` and added 4 test cases in `tests/dashboard/test_chat_router.py`.

### Endpoint Logic (`POST /api/chat/tabs/{tab_id}/clear`)

1. **404** — tab not found (via `_tab_service.get_tab`)
2. **400** — tab has no `opencode_session_id` (nothing to clear)
3. **Pi runtime path** (`tab.runtime == "pi"`):
   - Check `pi_runtime` health; 503 if unavailable
   - Resolve `project_directory` from the project's `repo_root`
   - Call `await pi_runtime.create_session(model=tab.model, directory=project_directory or None)`
4. **OpenCode path** (default):
   - Health gate via `Depends(_check_runtime_healthy)`; 503 if unhealthy
   - Resolve `project_directory` from the project's `repo_root`
   - Call `await client.create_session(model=tab.model, directory=project_directory or None)`
5. **Relay cleanup**: Call `await relay_manager.drop_relay(tab_id)` to close the old SSE relay before switching sessions
6. **DB update**: Set `tab.opencode_session_id = new_sid`, `db.commit()`, `db.refresh(tab)`
7. **Return**: `{"tab": _tab_to_dict(tab)}` with status 200

The `drop_relay` mock was also added to `_make_relay_manager()` in the test helper.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/chat.py` | Added `clear_tab` async handler (~60 lines, between `reply_permission` and `_apply_ai_assistant_allowlist`) |
| `tests/dashboard/test_chat_router.py` | Added `rm.drop_relay = AsyncMock()` to `_make_relay_manager()`; added `TestClearTab` class with 4 test methods |

---

## Test Results

```
tests/dashboard/test_chat_router.py::TestClearTab::test_clear_tab_not_found       PASSED
tests/dashboard/test_chat_router.py::TestClearTab::test_clear_tab_no_session      PASSED
tests/dashboard/test_chat_router.py::TestClearTab::test_clear_tab_returns_updated_tab  PASSED
tests/dashboard/test_chat_router.py::TestClearTab::test_clear_tab_runtime_unavailable  PASSED
==================== 4 passed, 45 deselected ====================
```

---

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ ok — "809 files already formatted" |
| `make typecheck` | ✅ ok — "Success: no issues found in 267 source files" |
| `make lint` | ✅ ok — "All checks passed!" |

---

## TDD Evidence

The worktree already had the endpoint code and tests written (from a previous attempt in this same worktree). The 4 tests pass on first run, confirming GREEN state. The only fix needed was 2 docstring lines exceeding the 100-char ruff line limit (E501) — corrected to pass lint.

---

## Notes / Observations

- The `clear_tab` handler was already present in `chat.py` when I arrived — it appears to have been implemented in a previous session in this worktree. The test file was similarly already prepared but the docstrings needed minor fixup.
- The `RelayManager.drop_relay(tab_id)` call in the handler is correct — it stops the relay pump for the old session and removes it from the manager's dict before the new session is created.
- The `Project` import from `orch.db.models` was already present in `chat.py` (needed for `db.get(Project, tab.project_id)`).
- No migrations needed — `opencode_session_id` column already exists on `chat_tabs`.
- The endpoint handles both Pi and OpenCode runtimes correctly.