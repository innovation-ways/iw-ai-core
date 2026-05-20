# CR-00063_S01_Frontend_prompt

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step makes NO database or migration changes. Frontend-only.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00063 --json`
- `ai-dev/active/CR-00063/CR-00063_CR_Design.md` — Design document
- `dashboard/static/chat_assistant/chat.js` — Primary file to edit
- `dashboard/templates/chat_assistant/panel.html` — Panel template (read-only reference)
- `tests/dashboard/test_chat_panel_event_protocol.py` — Existing test to read + update if needed

## Output Files

- `ai-dev/active/CR-00063/reports/CR-00063_S01_Frontend_report.md` — Step report

## Context

You are fixing two related bugs in the AI Assistant chat panel:

1. **History rendering gap**: `_loadTabHistory()` in `dashboard/static/chat_assistant/chat.js` only renders user and assistant text messages. Tool call and tool result messages are silently skipped. After a browser restart, the chat window looks empty even though the runtime session has the full history.

2. **Silent error suppression**: The `.catch(function () { /* silently ignore */ })` at the end of `_loadTabHistory` swallows all fetch errors, leaving the user with an empty panel and no feedback.

3. **Tab selection fallback**: When `sessionStorage` is cleared (browser restart), `_bootstrapTabs` falls back to `_tabs[0]` (first in array). It should instead select the tab with the most recent `last_active_at` timestamp from the API response, which is a more reliable proxy for "last used".

## Requirements

### 1. Fix `_loadTabHistory` — render all message types

**Location**: `dashboard/static/chat_assistant/chat.js`, function `_loadTabHistory` starting around line 1669.

**Current code (lines 1680–1692)**:
```js
data.messages.forEach(function (entry) {
  var info = entry && entry.info;
  var parts = (entry && entry.parts) || [];
  if (!info) return;
  var text = parts
    .filter(function (p) { return p && p.type === 'text' && typeof p.text === 'string'; })
    .map(function (p) { return p.text; })
    .join('');
  if (info.role === 'user') {
    _appendUserMessage(text);
  } else if (info.role === 'assistant') {
    _appendOrUpdateAssistantMessage(tabId, info.id, text, true);
  }
});
```

**Required behavior**: For each message in `data.messages`:

- **role === 'user'**: Collect text parts and call `_appendUserMessage(text)` (existing behavior, keep).
- **role === 'assistant'**: Iterate over parts and handle each type:
  - `type === 'text'` parts: collect and call `_appendOrUpdateAssistantMessage(tabId, info.id, text, true)` (existing behavior).
  - `type === 'tool-use'` or `type === 'tool_use'` parts: call `_appendToolCall(part)` for each. The existing `_appendToolCall` helper is already used for live streaming — reuse it here.
  - `type === 'tool-result'` parts: call `_appendToolResult(part)` for each. Ditto.

**How to find the existing helpers**: Search `chat.js` for `function _appendToolCall` and `function _appendToolResult` to understand their expected argument shape. Mirror that argument shape when calling them from the history loop.

**Note on Pi runtime vs OpenCode**: The part type strings may differ slightly between runtimes. Read `orch/chat/pi/pi_runtime.py` and `orch/chat/opencode/client.py` to confirm the exact `type` values for tool-use and tool-result parts in each runtime. Handle both conventions (e.g., `'tool-use'` and `'tool_use'`) defensively.

**After the loop**, reset the assistant state:
```js
_tabCurrentAssistantEl[tabId] = null;
_tabCurrentAssistantId[tabId] = null;
```
This is already present in the current code — keep it.

### 2. Fix `_loadTabHistory` — replace silent error suppression

**Current code (line 1698)**:
```js
.catch(function () { /* silently ignore */ });
```

**Required change**: Replace with a user-visible error using the existing `_appendSystemMessage` helper:
```js
.catch(function (err) {
  _appendSystemMessage('Could not load chat history — ' + (err && err.message ? err.message : 'runtime unavailable'), 'error');
});
```

Also replace the silent early return at the non-OK response guard (line 1672):
```js
if (!r.ok) return null;
```
Change to:
```js
if (!r.ok) throw new Error('HTTP ' + r.status);
```
This ensures non-200 responses (503 runtime unavailable, 404 not found) flow into the `.catch` handler and show the error message.

### 3. Fix `_bootstrapTabs` — `last_active_at` fallback

**Location**: `dashboard/static/chat_assistant/chat.js`, function `_bootstrapTabs` around line 157.

**Current code (lines 182–185)**:
```js
var lastActive = sessionStorage.getItem('iw-chat-active-tab-' + _browserTabId);
var target = lastActive && _tabs.find(function (t) { return t.id === lastActive; });
_activateTab(target ? target.id : _tabs[0].id);
```

**Required change**: When `target` is falsy (sessionStorage cleared or stale), pick the tab with the most recent `last_active_at` rather than always picking index 0:
```js
var lastActive = sessionStorage.getItem('iw-chat-active-tab-' + _browserTabId);
var target = lastActive && _tabs.find(function (t) { return t.id === lastActive; });
if (!target && _tabs.length > 1) {
  // sessionStorage cleared — restore the most recently active tab
  target = _tabs.reduce(function (best, t) {
    if (!best) return t;
    var bestTs = best.last_active_at ? new Date(best.last_active_at).getTime() : 0;
    var tTs = t.last_active_at ? new Date(t.last_active_at).getTime() : 0;
    return tTs > bestTs ? t : best;
  }, null);
}
_activateTab(target ? target.id : _tabs[0].id);
```

Apply the same pattern inside the `setTimeout` retry block (around line 171–172) for consistency.

**Note**: `last_active_at` is already returned by `GET /api/chat/tabs` via `_tab_to_dict` in `dashboard/routers/chat.py`. No API changes are needed.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for:

- Tailwind CSS is prebuilt — if any new CSS classes are needed, append plain CSS rules to `dashboard/static/chat_assistant/chat.css` instead of using Tailwind (per the `make css` mitigation rule in CLAUDE.md).
- JS in `dashboard/static/` is vanilla ES5 — no ES6+ syntax (no arrow functions, no `const`/`let`, no template literals). Match the style of the existing `chat.js`.
- Use `_appendSystemMessage(text, type)` for all user-visible error messages. `type='error'` renders a red banner.
- `make lint` runs `node --check` on dashboard JS files. Run it before reporting done.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write a test in `tests/dashboard/test_chat_history_restore.py` that asserts `_loadTabHistory` handles tool-call parts and error responses. Since `chat.js` is vanilla JS (not a module), the test must use regex/grep-based assertions on the JS source, consistent with patterns in `tests/dashboard/test_chat_panel_event_protocol.py`. Example assertions:
   - The `_loadTabHistory` function body contains a reference to `_appendToolCall` (verifies tool call rendering is wired).
   - The `_loadTabHistory` function body contains a reference to `_appendToolResult`.
   - The `_loadTabHistory` function body does NOT contain `silently ignore` (verifies the silent catch is removed).
   - The `_bootstrapTabs` function body contains `last_active_at` (verifies the fallback logic).
2. **GREEN**: Apply the fixes above.
3. **REFACTOR**: Verify the existing `test_chat_panel_event_protocol.py` still passes — it checks `_loadTabHistory` exists.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — run and fix any formatting drift.
2. `make typecheck` — zero errors on touched files.
3. `make lint` — zero errors (includes `node --check` on JS and `scripts/check_templates.py` on templates).

## Test Verification (NON-NEGOTIABLE)

Run only targeted tests — do NOT run the full suite:

```bash
uv run pytest tests/dashboard/test_chat_history_restore.py -v
uv run pytest tests/dashboard/test_chat_panel_event_protocol.py -v
```

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "CR-00063",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/chat_assistant/chat.js",
    "tests/dashboard/test_chat_history_restore.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_chat_history_restore.py::test_load_tab_history_renders_tool_calls — AssertionError: ...",
  "blockers": [],
  "notes": ""
}
```
