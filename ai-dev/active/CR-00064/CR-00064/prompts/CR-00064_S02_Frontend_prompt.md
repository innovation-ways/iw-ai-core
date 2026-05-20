# CR-00064_S02_Frontend_prompt

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant
**Step**: S02
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step makes NO database or migration changes.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00064 --json`
- `ai-dev/active/CR-00064/CR-00064_CR_Design.md` — Design document
- `ai-dev/active/CR-00064/reports/CR-00064_S01_API_report.md` — S01 report (read to confirm endpoint path/response shape)
- `dashboard/templates/chat_assistant/composer.html` — Add Clear button here
- `dashboard/static/chat_assistant/chat.js` — Add `_clearChat()` and related logic
- `dashboard/static/chat_assistant/chat.css` — Add disabled state CSS rule
- `tests/dashboard/test_chat_clear_button.py` (new) — Write tests here
- `tests/dashboard/test_chat_templates.py` — May need updating

## Output Files

- `ai-dev/active/CR-00064/reports/CR-00064_S02_Frontend_report.md` — Step report

## Context

S01 added `POST /api/chat/tabs/{tab_id}/clear` to the backend. This step wires the UI: adds the Clear button to the composer template, implements the JS logic, and tracks button enabled/disabled state based on message history.

## Requirements

### 1. Add Clear button to `composer.html`

**File**: `dashboard/templates/chat_assistant/composer.html`

Add a `<button id="chat-assistant-clear">` in the Send/Abort row, positioned to the **left of the Abort button**. The current layout is:

```
[settings]  ...  [abort] [send]
```

After this change:

```
[settings]  ...  [clear] [abort] [send]
```

The button HTML (place inside the `<div class="flex items-center gap-2">` that contains abort and send):

```html
<button id="chat-assistant-clear"
        type="button"
        disabled
        class="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:bg-muted min-h-[44px] min-w-[44px]"
        aria-label="Clear chat history"
        title="Clear all messages and reset context">
  Clear
</button>
```

Start with `disabled` attribute set — the JS will enable it when history exists.

### 2. Add CSS for disabled state in `chat.css`

**File**: `dashboard/static/chat_assistant/chat.css`

Append a plain CSS rule (do NOT use `make css` / Tailwind):

```css
#chat-assistant-clear:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
```

### 3. Add `_tabHasHistory` tracking and `_updateClearButton()` in `chat.js`

**File**: `dashboard/static/chat_assistant/chat.js`

**3a. Add state variable** near the other per-tab maps at the top of the IIFE (around lines 25–38):

```js
var _tabHasHistory = {};  // tabId -> bool
```

**3b. Add `_updateClearButton()` function** (place near `_updateSendAbortButtons` around line 1733):

```js
function _updateClearButton() {
  var btn = document.getElementById('chat-assistant-clear');
  if (!btn) return;
  var hasHistory = _activeTabId ? (_tabHasHistory[_activeTabId] || false) : false;
  btn.disabled = !hasHistory;
}
```

**3c. Set `_tabHasHistory[tabId] = true`** in two places:

- Inside `_loadTabHistory` (in `chat.js`), after at least one message is appended (i.e., after the `data.messages.forEach` loop completes and at least one `_appendUserMessage` or `_appendOrUpdateAssistantMessage` was called). A simple approach: count rendered messages during the loop and set the flag if count > 0.
- Inside the SSE event handler `_handleEvent` — set `_tabHasHistory[tabId] = true` when the first `message.part.delta` or `message.part.added` event arrives for a tab (this covers the live-streaming case).

**3d. Reset `_tabHasHistory[tabId]`** in:

- `_clearMessages()` — add `if (_activeTabId) _tabHasHistory[_activeTabId] = false;` at the end. (Note: `_clearMessages` is also called on tab switch; that's fine — the flag is per-tab and `_activateTab` will reload history setting it back.)
- After a successful clear (see `_clearChat` below).

**3e. Call `_updateClearButton()`** wherever `_updateSendAbortButtons()` is called — add it as a sibling call. Search `chat.js` for every `_updateSendAbortButtons()` call and add `_updateClearButton()` immediately after each one.

### 4. Add `_clearChat()` function in `chat.js`

Add this function near `_sendPrompt` and `_abort`:

```js
function _clearChat() {
  if (!_activeTabId) return;
  if (!_tabHasHistory[_activeTabId]) return;
  if (!window.confirm('Clear chat history? This cannot be undone.')) return;

  var tabId = _activeTabId;
  fetch('/api/chat/tabs/' + encodeURIComponent(tabId) + '/clear', { method: 'POST' })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (data) {
      // Only act if this tab is still active
      if (tabId !== _activeTabId) return;

      // 1. Update the in-memory tab model with new session ID
      var newTab = data && data.tab;
      if (newTab) {
        _tabs = _tabs.map(function (t) { return t.id === tabId ? newTab : t; });
      }

      // 2. Close old EventSource and reset SSE tracking
      if (_tabEs[tabId]) {
        _tabEs[tabId].close();
        delete _tabEs[tabId];
      }
      sessionStorage.removeItem('iw-chat-last-eid-' + tabId);
      delete _tabSeenIds[tabId];

      // 3. Reset streaming / assistant state
      _tabStreaming[tabId] = false;
      _tabCurrentAssistantEl[tabId] = null;
      _tabCurrentAssistantId[tabId] = null;

      // 4. Clear DOM
      _clearMessages();

      // 5. Reset history flag and update button
      _tabHasHistory[tabId] = false;
      _updateClearButton();
      _updateSendAbortButtons();

      // 6. Show confirmation message
      _appendSystemMessage('Chat cleared.', 'info');

      // 7. Reconnect stream to new session
      _connectStream(tabId);
    })
    .catch(function (err) {
      _appendSystemMessage('Could not clear chat: ' + (err && err.message ? err.message : 'unknown error'), 'error');
    });
}
```

### 5. Wire the Clear button event listener in `chat.js`

Find where the Abort and Send buttons are wired (around lines 2098–2107). Add the Clear button wiring in the same block:

```js
var clearBtn = document.getElementById('chat-assistant-clear');
if (clearBtn) {
  clearBtn.addEventListener('click', function () { _clearChat(); });
}
```

### 6. Call `_updateClearButton()` on tab activation

In `_activateTab`, after `_updateSendAbortButtons()` is called, add `_updateClearButton()`.

## Project Conventions

- **ES5 only** — no arrow functions, no `const`/`let`, no template literals.
- **Plain CSS** for `#chat-assistant-clear:disabled` — append to `chat.css`, do NOT recompile Tailwind.
- **`make lint`** includes `node --check` on JS files — run it before reporting done.
- Use `_appendSystemMessage(text, 'info')` for the "Chat cleared" notice (renders a gray banner).

## TDD Requirement

**RED**: Write `tests/dashboard/test_chat_clear_button.py` first. Use regex/grep assertions on the JS and template source (same pattern as `test_chat_panel_event_protocol.py`). Tests to write:

1. `test_clear_button_present_in_composer` — `composer.html` contains `id="chat-assistant-clear"`.
2. `test_clear_button_starts_disabled` — `composer.html` contains `disabled` on the clear button.
3. `test_clear_chat_function_exists` — `chat.js` contains `function _clearChat`.
4. `test_tab_has_history_tracking` — `chat.js` contains `_tabHasHistory`.
5. `test_update_clear_button_function` — `chat.js` contains `function _updateClearButton`.
6. `test_clear_calls_confirm` — `chat.js` `_clearChat` body contains `window.confirm`.
7. `test_clear_calls_api` — `chat.js` `_clearChat` body contains `/clear`.
8. `test_clear_removes_eid` — `chat.js` `_clearChat` body contains `removeItem`.

Run: `uv run pytest tests/dashboard/test_chat_clear_button.py -v` — all should fail first (RED).

**GREEN**: Implement the changes. Re-run — all pass.

**REFACTOR**: Run `tests/dashboard/test_chat_templates.py` — update if the composer template assertions need updating.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_chat_clear_button.py tests/dashboard/test_chat_templates.py -v --no-header
```

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "frontend-impl",
  "work_item": "CR-00064",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat_assistant/composer.html",
    "dashboard/static/chat_assistant/chat.js",
    "dashboard/static/chat_assistant/chat.css",
    "tests/dashboard/test_chat_clear_button.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_chat_clear_button.py::test_clear_button_present_in_composer — AssertionError: ...",
  "blockers": [],
  "notes": ""
}
```
