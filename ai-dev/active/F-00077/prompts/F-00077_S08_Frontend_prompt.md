# F-00077_S08_Frontend_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step**: S08
**Agent**: frontend-impl

---

## ⛔ Docker / Migrations off-limits

Same constraints. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md` — sections: Frontend Changes, AC1, AC3, AC4, AC5, Boundary Behavior (localStorage missing, cookie missing)
- `ai-dev/active/F-00077/reports/F-00077_S07_API_report.md`
- `dashboard/static/chat/composer.js` — current implementation. KEY references:
  - send-handler at lines 261-344
  - `conversationHistory = []` at line 281 (DELETE)
  - request body assembly at lines 293-301
  - SSE callbacks at lines 311-340
- `dashboard/static/chat/stream.js` — SSE parser, current event types: token, phase, citation, image, error, done
- `dashboard/static/chat/panel.js` — collapse/expand, resize, drawer, keyboard shortcuts
- `dashboard/templates/chat/panel.html` — chat panel structure (header has a collapse button at line 23-29)
- `dashboard/CLAUDE.md` — htmx + Tailwind conventions

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S08_Frontend_report.md`
- `dashboard/static/chat/composer.js` — MODIFIED
- `dashboard/static/chat/stream.js` — MODIFIED (handle `meta` event)
- `dashboard/static/chat/panel.js` — MODIFIED (replay-on-open, "New chat" handler, TTL rotation)
- `dashboard/templates/chat/panel.html` — MODIFIED (add "New chat" button)
- Test files (see Tests section)

## Context

You are wiring the chat UI to the new memory APIs from S07. Each browser session gets a `conversation_id` per `(project_id, module_path)` cached in localStorage; on chat-panel open, prior messages are replayed; "New chat" creates a fresh conversation; the SSE `meta` preamble captures the server-assigned id.

Read the design FIRST. Then `dashboard/CLAUDE.md` for htmx/Tailwind notes.

## Requirements

### 1. localStorage helpers (top of `panel.js` or new `state.js` — your call)

Add small helpers:

```js
const TTL_MS = 4 * 60 * 60 * 1000; // 4 hours

function chatStateKey(projectId, modulePath) {
  return `iw_chat_conv_${projectId}_${modulePath || 'arch'}`;
}

function getCachedConversation(projectId, modulePath) {
  try {
    const raw = localStorage.getItem(chatStateKey(projectId, modulePath));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed.conversation_id || !parsed.last_active_at) return null;
    if (Date.now() - parsed.last_active_at > TTL_MS) return null; // stale
    return parsed.conversation_id;
  } catch (e) {
    return null; // localStorage blocked / quota / corrupt
  }
}

function setCachedConversation(projectId, modulePath, conversationId) {
  try {
    localStorage.setItem(
      chatStateKey(projectId, modulePath),
      JSON.stringify({ conversation_id: conversationId, last_active_at: Date.now() })
    );
  } catch (e) { /* graceful no-op */ }
}

function clearCachedConversation(projectId, modulePath) {
  try { localStorage.removeItem(chatStateKey(projectId, modulePath)); } catch (e) {}
}
```

All access wrapped in try/catch — incognito + privacy modes block `localStorage` and we must not crash.

### 2. `composer.js` modifications

- Delete the line `var conversationHistory = [];` (line 281).
- Replace it with:
  ```js
  var cachedConvId = window.iwChatState && window.iwChatState.getCachedConversation
    ? window.iwChatState.getCachedConversation(projectId, modulePath)
    : null;
  ```
- Update the `body` object (line 293-301) — remove `conversation_history`, add `conversation_id`:
  ```js
  var body = {
    question: question,
    context_level: contextLevel,
    context_doc_id: contextDocId,
    module_path: modulePath,
    module_name: moduleName,
    conversation_id: cachedConvId,
    context_chips: contextChips_data,
  };
  ```
- In the `streamAnswer` callbacks, add `onMeta`:
  ```js
  onMeta: function (data) {
    if (data && data.conversation_id) {
      window.iwChatState.setCachedConversation(projectId, modulePath, data.conversation_id);
    }
  },
  ```
- After a successful `onDone` callback, refresh `last_active_at` by calling `setCachedConversation` again with the same id (so the TTL resets).

### 3. `stream.js` modifications

The SSE parser needs to recognize the new `event: meta` frame. Read the current parser end-to-end and add a `meta` branch alongside `token`/`phase`/`citation`/`image`/`error`/`done`:

```js
} else if (eventType === 'meta') {
  try {
    const data = JSON.parse(eventData);
    if (callbacks.onMeta) callbacks.onMeta(data);
  } catch (e) { /* malformed; skip */ }
}
```

`callbacks.onMeta` is documented in the streamAnswer JSDoc.

### 4. `panel.js` modifications

a) **"New chat" button handler**: read the button via `document.getElementById('chat-new-btn')`. On click:
   - Call `clearCachedConversation(projectId, modulePath)`.
   - Reset DOM: clear `#chat-messages` children except the empty-state node and the scroll anchor; show the empty state.
   - Optional: announce "New chat" via aria-live="polite" for accessibility.

b) **Replay on open**: when the panel transitions from collapsed→expanded (existing collapse handler), if a cached conversation_id exists for `(projectId, modulePath)`:
   - Fetch `GET /api/projects/{projectId}/conversations/{cid}/messages`.
   - On 404: clear localStorage and show empty state.
   - On 200: render each message into `#chat-messages` using the existing message-bubble templates. The shape is:
     - User messages → `appendUserBubble(content)`.
     - Assistant messages → render via the existing assistant renderer with `metadata.render_id` if present (no streaming — just static markdown).
   - Disable replay if there's only one message AND it's the user's first turn that streamed without an assistant reply (defensive).

c) **TTL rotation**: when the user clicks Send, the composer already calls `getCachedConversation` which returns null on stale. But ALSO: every minute (setInterval), refresh the visible "active conversation indicator" — if any UI shows it. (Skip the indicator for v1 if the design doesn't call for it.)

d) **Page-load auto-expand**: if the panel was previously expanded (existing localStorage flag for `iw_chat_collapsed`), trigger the replay path on `DOMContentLoaded`. Reuse the same handler used by the collapse→expand transition.

### 5. `panel.html` modifications

Add a "New chat" button to the header (line 21 onwards). Place it BEFORE the collapse button:

```html
<button id="chat-new-btn"
        class="tap inline-flex items-center justify-center text-xs px-2 py-1 rounded border border-border hover:bg-muted"
        aria-label="Start a new chat (clears history)">
  <svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
  </svg>
  New
</button>
```

Reuse existing Tailwind utility classes; do not introduce new ones (the JIT purger is not re-run during agent work).

After modifying templates, run:
```bash
make css
```

This regenerates `dashboard/static/styles.css`. Commit the regenerated file.

### 6. Tests

`tests/frontend/test_composer_state.py` (or wherever existing JS tests live):
- If the project has a JS test runner (Vitest/Jest): write unit tests for `getCachedConversation` / `setCachedConversation` / `clearCachedConversation`.
- TTL rotation: stub `Date.now()` to be `last_active_at + 5h` → `getCachedConversation` returns null.
- localStorage throws → all helpers return null / no-op (no exception escapes).

If no JS test runner is configured, fall back to a Python-side smoke test that loads the page via TestClient and asserts the `<button id="chat-new-btn">` is present in the rendered HTML.

`tests/dashboard/test_chat_panel_renders_new_chat_button.py`:
- TestClient GET `/project/iw-ai-core/code` → response contains `<button id="chat-new-btn"`.
- Snapshot asserts the panel template includes the new button via Beautiful Soup or similar.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- Tailwind classes only — no inline styles.
- `make css` after editing templates (the script is in the Makefile).
- Use existing utility helpers (`appendUserBubble`, `createAssistantRenderer`) rather than reimplementing.
- Vanilla JS — no framework.

## TDD Requirement

Write the rendering-snapshot test first. Implement after.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make css` (regenerate stylesheet — commit the diff)

## Test Verification

1. `make test-unit`
2. `make test-frontend` (if configured) OR python-side rendering tests
3. `make test-integration` (selectively for affected dashboard tests)

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "frontend-impl",
  "work_item": "F-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/chat/composer.js",
    "dashboard/static/chat/stream.js",
    "dashboard/static/chat/panel.js",
    "dashboard/templates/chat/panel.html",
    "dashboard/static/styles.css",
    "tests/dashboard/test_chat_panel_renders_new_chat_button.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "make css ran cleanly; resulting styles.css diff committed"
}
```
