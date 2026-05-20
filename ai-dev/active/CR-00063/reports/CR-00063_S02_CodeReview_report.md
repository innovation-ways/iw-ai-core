# CR-00063 S02 Code Review Report

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Step**: S02
**Agent**: CodeReview
**Completion**: `complete`

---

## What Was Reviewed

Reviewed S01 output for CR-00063: fixes to `_loadTabHistory` (render all message types, surface errors) and `_bootstrapTabs` (last_active_at fallback).

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/static/chat_assistant/chat.js` | Three fixes applied: tool-call/result rendering in `_loadTabHistory`, error surfacing, `last_active_at` fallback in `_bootstrapTabs` |
| `tests/dashboard/test_chat_history_restore.py` | New TDD test file (5 tests) covering all three fixes + silent error removal |

---

## Architecture & Code Quality Review

### AC1 — Tool call/result rendering in `_loadTabHistory`

- `_loadTabHistory` (line 1508–1553) iterates `data.messages`, extracts text parts, renders user/assistant text, then **iterates all `parts`** inside assistant entries and dispatches on `p.type`:
  - `p.type === 'tool-use'` or `'tool_use'` → calls `_appendToolCall(p.name, p.input)`
  - `p.type === 'tool-result'` or `'tool_result'` → calls `_appendToolResult(...)`
- Both OpenCode (`tool-use`) and Pi (`tool_use`) conventions are handled defensively.
- **Reuses existing helpers** (`_appendToolCall`, `_appendToolResult`) — no duplication.
- ✅ PASS

### AC2 — Error surfacing instead of silent catch

- `if (!r.ok) throw new Error('HTTP ' + r.status);` — non-OK responses throw, flow into `.catch`.
- `.catch(function (err) { _appendSystemMessage('Could not load chat history \u2014 ' + err.message, 'error'); })` — user-visible red banner.
- `"silently ignore"` removed from `_loadTabHistory`.
- ✅ PASS

### AC3 — `last_active_at` fallback in `_bootstrapTabs`

- Applied in two places: main `_fetchTabs` callback (line 196–205) and `setTimeout` retry block (line 174–185).
- Uses `t.last_active_at ? new Date(t.last_active_at).getTime() : 0` to handle null/undefined timestamps gracefully (tabs without timestamps get 0, won't win the sort).
- Applied only when `tabs.length > 1` — safe guard.
- ✅ PASS

### AC4 — Text-only conversations (no regression)

- Existing user/assistant text rendering logic (`_appendUserMessage`, `_appendOrUpdateAssistantMessage`) preserved and unchanged.
- Tool-call/result rendering only fires inside the `info.role === 'assistant'` branch.
- ✅ PASS

### ES5 Compliance

- No arrow functions, no `const`/`let`, no template literals — matches existing `chat.js` style.
- All new code uses `function () {}`, `var`, and string concatenation (`+`).
- ✅ PASS

### Security

- `_appendToolCall` and `_appendToolResult` both escape via `_escHtml()` before `innerHTML` insertion.
- `_appendSystemMessage` uses `textContent` (not `innerHTML`) — inherently safe.
- ✅ PASS

### Test File

- `tests/dashboard/test_chat_history_restore.py` present in changed files.
- 5 tests: tool calls, tool results, silent error removal, non-OK throw, `last_active_at` fallback.
- TDD RED evidence in S01 report: 4 failed / 1 passed on first run.
- ✅ PASS

---

## Pre-Review Lint & Format Gate

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed (ruff + check_templates.py + node --check on chat.js) |
| `make format` | ✅ All files already formatted |

---

## Test Verification

```
tests/dashboard/test_chat_history_restore.py         — 5 passed
tests/dashboard/test_chat_panel_event_protocol.py  — 8 passed
================================ 13 passed in 12.21s
```

No regressions. Coverage failure is expected (total of 4%) for targeted JS unit tests — unrelated to this change.

---

## Findings

No CRITICAL or HIGH findings.

| ID | Severity | Category | Finding |
|----|----------|----------|---------|
| F1 | LOW | Observation | `chat.js` still has one `.catch(function () { /* silently ignore */ })` at line 1714 inside `_refreshModels` — unrelated to this CR's scope but same pattern worth noting for future cleanup |

---

## Verdict

**PASS** — All acceptance criteria met, code quality verified, tests pass, lint clean.