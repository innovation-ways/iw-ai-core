# CR-00063 S01 Frontend Report

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Step**: S01
**Agent**: frontend-impl
**Completion**: `complete`

---

## What Was Done

Implemented three related fixes in `dashboard/static/chat_assistant/chat.js`:

### 1. `_loadTabHistory` — render all message types (tool calls + tool results)

The history-loading loop previously only handled `role === 'user'` (text) and `role === 'assistant'` (text).
After the fix, when iterating `data.messages`, the code also iterates over each part:

- `type === 'tool-use'` or `type === 'tool_use'` → calls `_appendToolCall(p.name, p.input)`
- `type === 'tool-result'` or `type === 'tool_result'` → calls `_appendToolResult(p.content)`

Both conventions are handled defensively: opencode uses `'tool-use'` / `'tool-result'`, Pi uses
`'tool_use'` / `'tool_result'`.

### 2. `_loadTabHistory` — replace silent error suppression

- `if (!r.ok) return null;` → `if (!r.ok) throw new Error('HTTP ' + r.status);`
  This ensures non-OK responses (503, 404, etc.) flow into `.catch`.
- `.catch(function () { /* silently ignore */ })` → `.catch(function (err) { _appendSystemMessage(...); })`
  Users now see a red banner: "Could not load chat history — runtime unavailable" instead of a silently empty panel.

### 3. `_bootstrapTabs` — `last_active_at` fallback

When `sessionStorage` is cleared (browser restart), the code now compares `last_active_at`
timestamps across all tabs and selects the one with the most recent timestamp instead of blindly
falling back to index 0. Applied both in the main `_fetchTabs` callback and in the `setTimeout`
retry block.

`last_active_at` is already returned by `GET /api/chat/tabs` via `_tab_to_dict` — no API changes needed.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/static/chat_assistant/chat.js` | Three fixes: tool-call/tool-result rendering in `_loadTabHistory`, error surfacing, `last_active_at` fallback in `_bootstrapTabs` |
| `tests/dashboard/test_chat_history_restore.py` | New TDD test file: 5 regex-based tests covering all three fixes |

---

## Test Results

```
tests/dashboard/test_chat_history_restore.py     — 5 passed
tests/dashboard/test_chat_panel_event_protocol.py — 8 passed (existing, unaffected)
================================ 13 passed in 12.32s
```

TDD RED evidence (first run before applying fixes):
```
FAILED tests/dashboard/test_chat_history_restore.py::test_load_tab_history_renders_tool_calls
  AssertionError: _loadTabHistory must call _appendToolCall for tool-use parts
FAILED tests/dashboard/test_chat_history_restore.py::test_load_tab_history_renders_tool_results
  AssertionError: _loadTabHistory must call _appendToolResult for tool-result parts
FAILED tests/dashboard/test_chat_history_restore.py::test_load_tab_history_throws_on_non_ok
  AssertionError: _loadTabHistory must throw on non-ok response so .catch fires
FAILED tests/dashboard/test_chat_history_restore.py::test_bootstrap_tabs_uses_last_active_at_fallback
  AssertionError: _bootstrapTabs must compare `last_active_at` timestamps
(4 failed, 1 passed in 16.85s)
```

After GREEN (fixes applied): all 5 passed.

---

## Preflight

| Gate | Result |
|------|--------|
| `make format` | fixed: `test_chat_history_restore.py` trailing newline + ruff format |
| `make typecheck` | ok: mypy 0 errors |
| `make lint` | ok: ruff + `scripts/check_templates.py` + `node --check` on `chat.js` |

---

## Blockers

None.

---

## Notes

- The function-body extractor in the test file was updated to use a brace-depth counter instead
  of the simple `\n  }\n` terminator, because `_loadTabHistory` contains nested `.then()` function
  expressions that each end with `\n  }` — the naive regex was truncating the function body before
  the tool-call rendering code.
- The `_appendToolCall` / `_appendToolResult` argument shapes used in the history loop
  (`p.name`, `p.input`, `p.content`) mirror the actual field names from both opencode and Pi
  runtime message schemas.