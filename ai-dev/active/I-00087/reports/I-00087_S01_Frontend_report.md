# I-00087 S01 Frontend Implementation Report

## What Was Done

Rewrote three sections of `dashboard/static/chat_assistant/chat.js` to align the frontend with the opencode 1.15 wire protocol.

### Change 1: `_connectStream` listener list (namedEvents)

Replaced the old stale listener array (`message.part`, `message.snapshot`, `message.complete`, `tool.call`, `tool.result`, `permission.asked`, `session.idle`, `error`, `gap`, `reconnecting`) with the correct set:

**opencode SDK events (from `orch/chat/filters.py` INTERESTING_EVENTS):**
- `message.part.updated` (was missing — caused all streaming text to be dropped)
- `tool.execute.before` (was `tool.call` — wrong name)
- `tool.execute.after` (was `tool.result` — wrong name)
- `permission.asked`
- `permission.replied` (was missing)
- `session.idle`
- `session.updated` (was missing)
- `session.error` (was missing)

**Additional opencode SDK events:**
- `message.part.delta` (streaming token delta)
- `message.updated`
- `message.part.removed`
- `message.removed`
- `session.status`

**Relay-synthesised events (unchanged):**
- `gap`, `reconnecting`, `error`, `relay.error`

Added a comment pointing to `orch/chat/filters.py:INTERESTING_EVENTS` as source of truth.

### Change 2: `_handleEvent` payload extraction

Added a comment block documenting the asymmetry between opencode-native events (payload under `properties`) and relay-synthesised events (flat `data` shape).

Rewrote all handler branches:

- **`message.part.delta`**: reads `props.delta`, uses `props.messageID` as dedup key.
- **`message.part.updated`**: reads `props.delta || props.part.text`, uses `props.part.messageID` as dedup key.
- **`message.part.removed`**: no-op (parts are accumulated into bubbles, no individual part DOM nodes).
- **`message.updated`**: reads `props.info` (Message), marks bubble final when `info.time.completed` is set, renders error bubble if `info.error` is set.
- **`message.removed`**: no-op (safe — no per-message DOM key used in current implementation).
- **`tool.execute.before`**: appends system bubble with `props.tool`.
- **`tool.execute.after`**: marks tool complete with `props.tool` and optional `props.duration`.
- **`permission.asked`**: re-wired to read `props.id` (PermissionRequest.id) as the request id instead of the non-existent `data.request_id`.
- **`permission.replied`**: dismisses the approval modal.
- **`session.idle`**: preserved existing behaviour; reads from `props || data` for backwards compat.
- **`session.status`**: updates streaming indicators based on `props.status.type`.
- **`session.error`**: renders error bubble from `props.error`.
- **`session.updated`**: no-op.
- **`gap`, `reconnecting`, `error`, `relay.error`**: preserved existing flat-data behaviour.

### Change 3: `_loadHistory` iteration

Rewrote to iterate `Array<{ info: Message, parts: Array<Part> }>` (the actual opencode `SessionMessagesResponses` shape), replacing the broken `m.role` / `m.content` read:

- Reads `entry.info.role` and `entry.info.id`
- Concatenates `parts[].text` for parts with `type === 'text'`
- Passes `info.id` as the dedup key for assistant messages

### Change 4: `_showApprovalModal` data extraction

Updated to read the `PermissionRequest` shape (`permission` for tool name, `patterns` for args, `id` for request id) with fallbacks to legacy keys.

## Files Changed

- `dashboard/static/chat_assistant/chat.js` — only production file modified

## Test Results

```
tests/unit/test_chat_client.py         17 passed
tests/dashboard/test_chat_router.py    35 passed
Total: 52 passed, 0 failed
```

## Quality Gates

- `node --check dashboard/static/chat_assistant/chat.js`: OK
- `make lint`: All checks passed
- `make format`: 742 files already formatted (no changes needed)
- `make typecheck`: Success: no issues found in 255 source files

## Session-Continuity Grep Audit

### 1. sessionStorage key set/read (`iw-chat-session-`)
```
107:    sessionStorage.removeItem('iw-chat-session-' + _tabId);
117:    sessionStorage.setItem('iw-chat-session-' + _tabId, sid);
135:    var cached = sessionStorage.getItem('iw-chat-session-' + _tabId);
160:        sessionStorage.setItem('iw-chat-session-' + _tabId, _sid);
```
PRESERVED.

### 2. `last_event_id=` URL param in `_connectStream`
```
174:      url += '?last_event_id=' + encodeURIComponent(_lastSeenId);
```
PRESERVED.

### 3. `_loadHistory` called after reconnect
```
118:    _loadHistory(sid);   (switchSession)
139:      _loadHistory(_sid); (_ensureSession on cached session)
```
PRESERVED.

### 4. `newSession()` wipes sessionStorage, messages, `_seenIds`
```
101:  function newSession() {
107:    sessionStorage.removeItem('iw-chat-session-' + _tabId);
```
PRESERVED.

### 5. `switchSession` / `newSession` functions present
```
101:  function newSession() {
111:  function switchSession(sid) {
```
PRESERVED. Both exported on `window.iwChat`.

### 6. `_renderChip` present and called
```
83:    _renderChip();   (setContext)
89:    _renderChip();   (clearContext)
660:  function _renderChip() {
```
PRESERVED.

## Issues / Notes

- The task prompt mentioned `permission.updated` as the new wire name but the opencode SDK types (`EventPermissionAsked.type = "permission.asked"`) and `INTERESTING_EVENTS` both confirm `permission.asked` is correct. The approval modal handler was re-wired to read `properties.id` (PermissionRequest.id) instead of the non-existent `data.request_id`.
- `tool.execute.before`/`tool.execute.after` event types from `INTERESTING_EVENTS` are handled, but these event names do not appear in the opencode SDK type union (`Event`). The SDK uses `ToolPart` snapshots via `message.part.updated` to communicate tool state. The `tool.execute.before`/`after` handlers are in place as specified; they will no-op if the events are never emitted.
- `message.part.delta` (type `"message.part.delta"`) is the primary streaming text event per the SDK; it was added to the listener list even though it is not in `INTERESTING_EVENTS` since it is the actual wire event for token-by-token streaming.
