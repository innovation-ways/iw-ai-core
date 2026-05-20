# CR-00069_S01_Frontend_prompt

**Work Item**: CR-00069 — AI Assistant — Remove Clear Button Confirmation Dialog
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step writes no migrations. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00069 --json`
- `ai-dev/active/CR-00069/CR-00069_CR_Design.md` — Design document
- `dashboard/CLAUDE.md` — dashboard conventions
- `dashboard/static/chat_assistant/chat.js` — AI Assistant JS (target)
- `tests/dashboard/test_chat_clear_button.py` — existing clear-button test (target)

## Output Files

- `dashboard/static/chat_assistant/chat.js` — modified
- `tests/dashboard/test_chat_clear_button.py` — modified
- `ai-dev/work/CR-00069/reports/CR-00069_S01_Frontend_report.md` — report

## Context

The AI Assistant Clear button is wired to `_clearChat()` in `chat.js`.
`_clearChat()` currently shows a native confirmation popup before clearing:

```
if (!window.confirm('Clear chat history? This cannot be undone.')) return;
```

This step removes that popup so a click clears the chat immediately. The Clear
button is already `disabled` when there is no history, and `_clearChat()` keeps
its early-return guards (`_activeTabId`, `_tabHasHistory[_activeTabId]`), so the
removal is safe.

## Task

### 1. `chat.js` — remove the confirmation line

In `dashboard/static/chat_assistant/chat.js`, inside the `_clearChat()`
function, remove **only** the `window.confirm` line:

```
if (!window.confirm('Clear chat history? This cannot be undone.')) return;
```

Delete that single line entirely. Do NOT remove or alter:
- The `if (!_activeTabId) return;` guard.
- The `if (!_tabHasHistory[_activeTabId]) return;` guard.
- The `fetch('/api/chat/tabs/' + ... + '/clear', ...)` call and its `.then` /
  `.catch` chain.
- The SSE/streaming reset, DOM clear, button-state update, stream reconnect.
- The `_appendSystemMessage('Chat cleared.', 'info')` call.

After the edit, `_clearChat()` proceeds directly from the two guards to the
`fetch` call. The function body must contain no reference to `window.confirm`.

### 2. `test_chat_clear_button.py` — invert the confirm test

In `tests/dashboard/test_chat_clear_button.py`:

- The test `test_clear_calls_confirm` currently asserts that the string
  `window.confirm` IS present in `chat.js` and enforces "must show a
  confirmation dialog". Invert it: rename it to `test_clear_has_no_confirm`
  (or similar) and change the assertion so it requires that the `_clearChat()`
  body does **not** reference `window.confirm`. Scope the assertion to the
  `_clearChat` function body — extract the body yourself (e.g. slice the
  `chat.js` source from `function _clearChat` to its closing brace) and assert
  `window.confirm` is absent from that slice. Note: the other tests in this
  file currently use blunt whole-file `in js` checks, so a whole-file
  `"window.confirm" not in js` check would also pass today; scoping to
  `_clearChat` is preferred because it keeps the test precise — an unrelated
  `window.confirm` added elsewhere in `chat.js` later cannot turn this test
  into a false failure.
- Update the module docstring's numbered test list at the top of the file so the
  entry for this test matches its new name and intent.
- Do NOT change the other tests in the file (`_clearChat` exists, button
  disabled-by-default, calls `/clear`, removes the eid key) — they must still
  pass unchanged.

## Constraints

- Pure behaviour change. Do NOT modify any Python outside the named test file,
  any router, the `composer.html` template, or the `/clear` endpoint.
- Keep the change minimal — this is a one-line removal plus a one-test
  inversion. Do NOT refactor `_clearChat()` or adjacent code.
- Do NOT leave commented-out dead code.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
uv run pytest tests/dashboard/test_chat_clear_button.py -v
```

`make lint` (includes `node --check` on `chat.js`) and `make format-check` must
pass with no new violations. The `test_chat_clear_button.py` run must pass —
all tests in that file green, including the inverted one.

## Subagent Result Contract

```bash
uv run iw step-done CR-00069 --step S01 \
  --report ai-dev/work/CR-00069/reports/CR-00069_S01_Frontend_report.md
```

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "CR-00069",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/chat_assistant/chat.js",
    "tests/dashboard/test_chat_clear_button.py"
  ],
  "tests_passed": true,
  "test_summary": "lint + format-check + test_chat_clear_button.py passed",
  "blockers": [],
  "notes": ""
}
```
