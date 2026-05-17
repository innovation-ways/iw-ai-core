# I-00087: AI Assistant chat panel does not render model responses (wire-protocol drift)

**Type**: Issue
**Severity**: High
**Created**: 2026-05-17
**Reported By**: Manual testing after shipping commit 88e1ed08 (Fix AI Assistant chat panel: models, skills, prompt shape, root path)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This work item does not touch container management — only frontend JS and tests.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work item leaves migrations unchanged (no DB schema changes).

## Description

The dashboard AI Assistant chat panel accepts a user prompt and opencode (`opencode serve` on port 4096) generates a streaming reply — but the panel never renders the assistant's text. Only the trailing "Session idle." status line appears at the end. Conversation history also fails to reload across page refresh or session switch. Net effect: from the user's point of view the assistant is mute.

Root cause is a wire-protocol drift between the frontend (`dashboard/static/chat_assistant/chat.js`) and the opencode SDK (`@opencode-ai/sdk`, version pinned by the installed opencode 1.15.0): the frontend registers event listeners and reads payloads using names/keys that opencode does not emit, and silently drops the events that opencode actually does emit.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key files for this work item:
- `dashboard/static/chat_assistant/chat.js` — the chat panel's client-side controller
- `orch/chat/filters.py` — backend normaliser (`INTERESTING_EVENTS` already lists the correct event names; treat this as the canonical contract on the Python side)
- `.opencode/node_modules/@opencode-ai/sdk/dist/gen/types.gen.d.ts` — opencode's authoritative TypeScript type definitions (the source of truth for wire-shape questions)
- `~/.local/share/opencode/log/*.log` — opencode's own log; useful for confirming what the runtime actually publishes
- `tests/dashboard/test_chat_router.py` and `tests/unit/test_chat_client.py` — existing test patterns

## Browser Evidence

Captured 2026-05-17 against the live dashboard (PID 141821) and opencode (PID 141826) before any fix in this item was attempted:

- `evidences/pre/I-00087-bug-no-assistant-reply.png` — screenshot of the chat panel after sending "say pong and nothing else" with model `minimax/MiniMax-M2.7` selected; only the user bubble plus "Session idle." render, no assistant message.
- `evidences/pre/I-00087-bug-snapshot.yml` — accessibility snapshot of the same state.
- `evidences/pre/I-00087-opencode-events.log` — excerpt from opencode's log showing the model DID respond: multiple `message.part.updated`, `message.part.delta`, and `message.updated` bus publishes for `session.id=ses_1cac422a4ffePtAhbH3gj8E0jG` before the final `session.idle`.

## Steps to Reproduce

1. Restart the dashboard (`./ai-core.sh dashboard restart`) so a fresh opencode subprocess is owned by the dashboard.
2. Open `http://localhost:9900/` in a browser and expand the AI Assistant panel (Ctrl+/).
3. Confirm the model selector is populated (this work depends on commit `88e1ed08` being merged; `minimax/MiniMax-M2.7` should be the default).
4. Type any prompt (e.g. `say pong and nothing else`) and click `Send ↵`.
5. Wait at least 10 seconds.

**Expected**: an assistant message bubble appears under the user bubble, streams the model's reply (token-by-token deltas), and finalises when opencode emits `session.idle`. Refreshing the page should reload the full conversation history (user + assistant turns).

**Actual**: the user bubble is rendered immediately; after a few seconds a single muted "Session idle." status line appears; the assistant's actual reply never renders even though opencode's own log shows the model produced multiple `message.part.delta` chunks plus `message.updated`. Refreshing the page or switching sessions clears the conversation entirely (history reload is silently broken too).

## Browser Verification Script

```bash
# Confirm dashboard + opencode are up
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9900/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:4096/global/health   # 401 means up; auth-protected

playwright-cli kill-all
playwright-cli open http://localhost:9900/

# Expand the AI Assistant panel (the snapshot ref for the expand button varies; snapshot first)
playwright-cli snapshot                                  # locate ref for "Expand AI Assistant panel"
playwright-cli click <ref-from-snapshot>

# Send a prompt
playwright-cli snapshot                                  # locate refs for the textbox + Send button
playwright-cli fill <textbox-ref> "say pong and nothing else"
playwright-cli click <send-button-ref>

sleep 12

# Inspect the conversation log
playwright-cli eval "() => { const log = document.querySelector('[role=\"log\"]'); return log ? log.innerText : 'no log'; }"

# Cross-check opencode's own log
tail -50 ~/.local/share/opencode/log/$(ls -t ~/.local/share/opencode/log/ | head -1) | grep -E "message.part|message.updated|session.idle"
```

The bug is reproduced when `innerText` ends with `\nSession idle.` and the opencode log clearly shows `message.part.delta` / `message.part.updated` / `message.updated` published in the same session.

## Root Cause Analysis

Three coupled defects, all in `dashboard/static/chat_assistant/chat.js`:

### Defect 1 — wrong listener names

`chat.js:187-191` (`_connectStream`) registers `EventSource.addEventListener` listeners for these names:

```
'message.part', 'message.snapshot', 'message.complete', 'message.updated',
'tool.call', 'tool.result', 'permission.asked',
'session.idle', 'error', 'gap', 'reconnecting'
```

Per `.opencode/node_modules/@opencode-ai/sdk/dist/gen/types.gen.d.ts` the actual event types opencode emits over `/event` (and that the relay forwards verbatim per `orch/chat/filters.py:40-71`) include:

| Wire name | Carries | Currently handled? |
|---|---|---|
| `message.part.updated` | `{part: Part, delta?: string}` — streaming token chunks and final part snapshot | NO (listener registered as `message.part`) |
| `message.part.removed` | `{sessionID, messageID, partID}` | NO |
| `message.updated` | `{info: Message}` | partial (listener exists but handler reads wrong keys — see Defect 2) |
| `message.removed` | `{sessionID, messageID}` | NO |
| `tool.execute.before` / `tool.execute.after` | tool invocations | NO (listener registered as `tool.call`/`tool.result`) |
| `permission.updated` / `permission.replied` | permission lifecycle | NO (listener registered as `permission.asked`) |
| `session.idle` | `{sessionID, ...}` | YES |
| `session.status`, `session.error`, `session.updated`, `session.created`, `session.deleted`, `session.compacted`, `session.diff` | session lifecycle | NO |

`EventSource.addEventListener('message.part', cb)` does NOT fire for an SSE frame whose `event:` line says `message.part.updated` — EventSource matches event names exactly, not by prefix. So every streaming-text frame is dropped on the floor. `message.updated` does fire its listener but Defect 2 below means the listener still extracts nothing renderable.

The backend constant `orch/chat/filters.py:28-37` (`INTERESTING_EVENTS`) already enumerates the correct names — proving the contract was understood at the relay layer; only the frontend was never aligned.

### Defect 2 — wrong payload extraction

`chat.js:209-298` (`_handleEvent`) extracts text via `data.text || data.content || data.delta`. Opencode payloads nest data under `properties`:

- `EventMessagePartUpdated.properties = {part: Part, delta?: string}` — text deltas live in `properties.delta`, finalised text in `properties.part.text` (for `TextPart`).
- `EventMessageUpdated.properties = {info: Message}` — the full message metadata; **opencode messages have no `content` field** — text lives only in the message's `parts[]`.
- `EventPermissionUpdated.properties` — permission lifecycle; the current handler reads `data.request_id` (wrong key).

So even when a listener does fire, the handler reads `undefined` and renders an empty bubble (or no bubble at all because empty text short-circuits `_appendOrUpdateAssistantMessage`).

### Defect 3 — history reload reads non-existent fields

`chat.js:513-535` (`_loadHistory`) iterates `data.messages` and reads `m.role` plus `m.content`. The opencode endpoint `GET /session/{id}/message` returns (per SDK):

```ts
Array<{info: Message, parts: Array<Part>}>
```

Where `Message = UserMessage | AssistantMessage` — both have `role` on `info`, never on the outer object — and neither has a `content` field; text lives in `parts[].text` (for `TextPart`). So `m.role` is always `undefined` → both branches of the `if` fall through → no history renders. This is silent — there is no error in the console.

This breaks the user's explicit requirement that "when the user interacts with the LLM it keeps the same session and context": session IDs persist correctly (`sessionStorage['iw-chat-session-' + _tabId]`), but the rendered history is empty on every reload, so the *visible* context is lost even though the underlying opencode session retains it.

### How this slipped through

The chat router (`dashboard/routers/chat.py`) and `orch/chat/filters.py` already knew the right event names — see `INTERESTING_EVENTS`. The frontend was written against an earlier opencode contract or a guess, and the dashboard tests cover the router/relay (`tests/dashboard/test_chat_router.py`) and the wire shape (`tests/unit/test_chat_client.py`) but never exercise the JS handler against representative opencode frames. The bug only became user-visible after commit `88e1ed08` fixed the upstream config/skills/prompt-shape bugs that previously prevented prompts from being accepted at all.

## Affected Components

| Component | File:line | Impact |
|---|---|---|
| `_connectStream` listener list | `dashboard/static/chat_assistant/chat.js:187-191` | Streaming text deltas and ~10 other event types are silently dropped (no listener registered) |
| `_handleEvent` payload extraction | `dashboard/static/chat_assistant/chat.js:209-298` | When a listener does fire, the handler reads wrong keys and renders nothing |
| `_loadHistory` row extraction | `dashboard/static/chat_assistant/chat.js:513-535` | Conversation history is silently empty on page refresh or session switch — user perceives "context lost" |

No backend changes required — `orch/chat/relay_manager.py` and `orch/chat/filters.py` already pass opencode events through with the correct names.

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|---|---|---|---|
| S01 | `frontend-impl` | Rewrite `_connectStream` listener list + `_handleEvent` payload extraction + `_loadHistory` for opencode 1.15 wire shape. Preserve all existing behaviour: session-ID persistence, stream resume via `Last-Event-ID`, abort, permission modal, context chip, reconnecting pill, slash menu. | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `tests-impl` | Reproduction + regression tests (see TDD Approach) | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `code-review-final-impl` | Global cross-agent review | — |
| S06 | `qv-gate` (lint) | `make lint` | — |
| S07 | `qv-gate` (format) | `make format-check` | — |
| S08 | `qv-gate` (typecheck) | `make type-check` | — |
| S09 | `qv-gate` (unit-tests) | `make test-unit` | — |
| S10 | `qv-gate` (integration-tests) | `make allure-integration` (timeout 900s) | — |
| S11 | `qv-browser` | End-to-end browser verification of the fix in the isolated worktree stack | — |
| S12 | `self-assess-impl` | Self-assessment (project has `self_assess = true`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: This work item does NOT touch `orch/db/migrations/versions/**`

### Code Changes

- **Files to modify**:
  - `dashboard/static/chat_assistant/chat.js` — the only production file changed
- **Files to add (tests)**:
  - `tests/dashboard/test_chat_panel_js_handler.py` — Python-driven tests that load `chat.js` into a Node subprocess (or, simpler, regex/AST inspection of the registered event names) and assert the listener set matches the opencode SDK's `INTERESTING_EVENTS` plus that handler payload-extraction paths exist for the known event types. See **TDD Approach** for the concrete test strategy.
- **Nature of change**: align frontend with opencode 1.15 wire protocol. No behavioural regressions in the surrounding code paths (session-ID persistence, abort, permissions, context chip) should be possible if the test suite below stays green.

#### Concrete event handling table (S01 must implement all rows)

| Wire event | Handler action | Payload extraction |
|---|---|---|
| `message.part.updated` | Append or update assistant bubble with streaming text | `(properties.delta) \|\| (properties.part && properties.part.text) \|\| ''` |
| `message.part.removed` | Remove the part from the assistant bubble (if it was rendered) | use `properties.partID` |
| `message.updated` | If `properties.info.role === 'assistant'` and the message has reached `time.completed`, mark the bubble final; if `properties.info.error` is set, render as error | inspect `properties.info` (a full `Message`) |
| `message.removed` | Remove the message bubble | `properties.messageID` |
| `tool.execute.before` | Render a one-line "🔧 {tool}" system bubble | `properties.tool` (tool name) |
| `tool.execute.after` | Mark the matching tool bubble complete (optionally with elapsed time) | `properties.tool`, `properties.duration` |
| `permission.updated` | Show approval modal | `properties.request_id` (or whatever the actual SDK field is — implementer to verify against types.gen.d.ts) |
| `permission.replied` | Dismiss approval modal | `properties.request_id` |
| `session.idle` | Mark streaming finished, show "Session idle." (existing behaviour — keep but read from `properties` not `data`) | `properties` (check for `permission_denied`, `aborted`) |
| `session.status` | Update streaming indicator (no visible bubble) | `properties.status` |
| `session.error` | Render error bubble | `properties.error` |
| `session.updated` | No-op (or refresh metadata) | `properties.info` |
| `gap` | Existing behaviour (gap warning) | `data` (relay-synthesised event, keeps `{event, data, id}` outer shape) |
| `reconnecting` | Existing behaviour (reconnecting pill) | `data` (relay-synthesised) |
| `error` | Existing behaviour (system bubble) | `data` (relay-synthesised) |

Note the asymmetry: opencode-native events wrap everything in `properties`; relay-synthesised events (`gap`, `reconnecting`, the relay's own `error` for upstream connection issues) use the flat `{event, data, id}` shape from `orch/chat/filters.py`. The handler must distinguish these — recommend: try `properties` first, fall back to `data`. Document this in a comment.

#### History reload (`_loadHistory`)

Rewrite the iteration:

```js
data.messages.forEach(function (entry) {
  var info = entry && entry.info;
  var parts = (entry && entry.parts) || [];
  if (!info) return;
  // Concatenate every TextPart's text for the rendered bubble.
  var text = parts
    .filter(function (p) { return p && p.type === 'text' && typeof p.text === 'string'; })
    .map(function (p) { return p.text; })
    .join('');
  if (info.role === 'user') {
    _appendUserMessage(text);
  } else if (info.role === 'assistant') {
    _appendOrUpdateAssistantMessage(info.id, text, true);
  }
});
```

Pass `info.id` as the dedup key so an in-flight assistant message stream doesn't double-render after a reconnect.

#### Session continuity invariants that MUST be preserved (per user requirement)

The S01 agent must NOT regress any of these — explicitly confirm in the step report:

1. `sessionStorage['iw-chat-session-' + _tabId]` is still set on session create and read on panel open (`_ensureSession`).
2. `_connectStream(sid)` still passes `?last_event_id=<id>` when `_lastSeenId` is set (relay replay-after-blip).
3. After a stream reconnect, `_loadHistory(sid)` is called so the user sees the conversation up to that point (existing call at `chat.js:139`).
4. `newSession()` still wipes `sessionStorage`, message log, and `_seenIds`.
5. `switchSession(sid)` still works (history panel feature — existing call at `chat.js:111`).
6. The context chip (`_renderChip`) is still rendered and dismissable (existing behaviour around `chat.js:543-559`).

## File Manifest

All files for this work item live under `ai-dev/active/I-00087/`:

| File | Type | Purpose |
|---|---|---|
| `I-00087_Issue_Design.md` | Design | This document |
| `I-00087_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `evidences/pre/I-00087-bug-no-assistant-reply.png` | Evidence | Pre-fix screenshot |
| `evidences/pre/I-00087-bug-snapshot.yml` | Evidence | Pre-fix accessibility snapshot |
| `evidences/pre/I-00087-opencode-events.log` | Evidence | Pre-fix opencode log excerpt |
| `prompts/I-00087_S01_Frontend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00087_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00087_S03_Tests_prompt.md` | Prompt | S03 test coverage |
| `prompts/I-00087_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00087_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-agent global review |
| `prompts/I-00087_S11_BrowserVerification_prompt.md` | Prompt | S11 qv-browser script |
| `prompts/I-00087_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment |

Reports are created during execution in `ai-dev/active/I-00087/reports/`.

## Test to Reproduce

Write a failing test that proves the bug exists. Because the bug is in browser JavaScript and the project's test stack is pytest, the most effective and lowest-risk approach is to **assert the contract** rather than spin up a JS runtime: parse `chat.js` and assert (a) the registered event-name set includes the opencode wire names the relay actually forwards, and (b) the handler code references the correct payload accessors.

**Test-file location** — `tests/dashboard/test_chat_panel_event_protocol.py` (uses the existing `dashboard` test directory; no FastAPI client required — pure file-read + regex/AST assertions, no testcontainer).

```python
"""Tests that pin the chat panel's wire-protocol contract against opencode SDK.

These tests would FAIL before the I-00087 fix (chat.js never listened for
`message.part.updated` and never read `properties.delta` / `properties.part.text`).
They PASS after the fix.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from orch.chat.filters import INTERESTING_EVENTS

CHAT_JS = Path(__file__).resolve().parents[2] / "dashboard/static/chat_assistant/chat.js"


def _registered_event_names(js_source: str) -> set[str]:
    """Extract every event name passed to `_es.addEventListener(<name>, …)`.

    Tolerant of both the array-form (`namedEvents.forEach`) and direct calls;
    matches the literal strings in the file regardless of formatting.
    """
    # Grabs strings appearing inside any array literal that is later iterated
    # to register listeners, plus any direct `addEventListener('X', …)` call.
    direct = set(re.findall(r"addEventListener\(\s*['\"]([\w.]+)['\"]", js_source))
    # Find the `namedEvents = [ ... ]` block(s) and pull every quoted string out.
    array_blocks = re.findall(
        r"namedEvents\s*=\s*\[([\s\S]*?)\]", js_source
    )
    array_names: set[str] = set()
    for block in array_blocks:
        array_names.update(re.findall(r"['\"]([\w.]+)['\"]", block))
    return direct | array_names


def test_chat_js_registers_every_interesting_event() -> None:
    """Every event in the backend's INTERESTING_EVENTS list must have a
    frontend listener; otherwise the relay forwards events the UI silently
    drops. This is the regression that broke I-00087.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    registered = _registered_event_names(js)
    missing = set(INTERESTING_EVENTS) - registered
    assert not missing, (
        f"chat.js is missing EventSource listeners for opencode events "
        f"that the relay forwards: {sorted(missing)}"
    )


def test_chat_js_reads_properties_delta_for_streaming_text() -> None:
    """opencode wraps every event payload under `properties.*`.  The handler
    must read `properties.delta` (streaming chunks) and `properties.part`
    (finalised text), not the old `data.text || data.content || data.delta`
    flat shape.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    assert "properties.delta" in js, (
        "_handleEvent must read properties.delta for message.part.updated frames"
    )
    assert "properties.part" in js, (
        "_handleEvent must read properties.part.text (or .part) for finalised text"
    )


def test_chat_js_history_reads_info_and_parts() -> None:
    """_loadHistory must iterate `{info, parts}` entries (opencode shape),
    not `{role, content}` (which doesn't exist on opencode messages).
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    # Find the _loadHistory function body
    m = re.search(r"function\s+_loadHistory\b[\s\S]*?\n\s*\}\s*\n", js)
    assert m, "_loadHistory function not found in chat.js"
    body = m.group(0)
    assert ".info" in body, (
        "_loadHistory must read entry.info.role / entry.info.id "
        "(opencode messages have no top-level role/content)"
    )
    assert ".parts" in body, (
        "_loadHistory must iterate entry.parts to extract text "
        "(opencode messages have no top-level content field)"
    )
```

The Tests step (S03) will add additional regression tests (see TDD Approach below).

## Browser Verification Test

After the fix, the qv-browser step (S11) re-runs the **Browser Verification Script** above, with these pass conditions:

1. After sending "say pong" with a model selected, the conversation log MUST contain an assistant bubble whose text matches what opencode's log shows the model produced. The exact string is non-deterministic (LLM output) but must be non-empty AND must NOT equal `"Session idle."` (that's the *system* message).
2. Refreshing the page (after the assistant reply finalises) MUST reload BOTH the user and assistant bubbles. Asserting the bubble count is >= 2 after refresh is sufficient.
3. No console errors appear at any point.

## Acceptance Criteria

### AC1: Streaming assistant replies render in real time

```
Given the AI Assistant panel is open with a model selected
When the user sends a prompt
And opencode generates a streaming reply (one or more `message.part.updated` events with non-empty `properties.delta`)
Then an assistant message bubble is created on first delta
And subsequent deltas are appended to that same bubble (token-by-token streaming)
And the bubble is finalised when opencode emits `session.idle` or a `message.updated` whose `info.time.completed` is set
```

### AC2: Session continuity — history reloads across refresh / session switch

```
Given the user has had a multi-turn conversation in the AI Assistant panel
When the user refreshes the page
Then the same opencode session is reused (sessionStorage key 'iw-chat-session-' + tabId is read)
And every prior user turn renders as a user bubble
And every prior assistant turn renders as an assistant bubble with its concatenated TextPart text
And the streaming indicator is correctly off (since session.idle has fired before refresh)
```

### AC3: Tool calls produce a visible breadcrumb

```
Given opencode invokes a tool during the assistant's turn
When the corresponding `tool.execute.before` event arrives
Then a system-style bubble appears with the tool name (e.g., "🔧 read")
And when `tool.execute.after` arrives that bubble is marked complete (optionally with elapsed time)
```

### AC4: Permission requests still surface the approval modal

```
Given opencode emits a `permission.updated` event (the actual wire name; the old code listened for the non-existent `permission.asked`)
When the event arrives
Then the existing approval modal is shown with the request details
And the existing reply path (`POST /api/chat/sessions/{sid}/permissions/{rid}`) still works on Allow / Deny
```

### AC5: Regression tests exist and protect the contract

```
Given the fix is applied
When `make test-unit` and `make test-integration` run
Then `tests/dashboard/test_chat_panel_event_protocol.py` (the file added in S03) passes
And the test would have failed against chat.js as it existed in commit 88e1ed08 (this is the RED evidence S03 must capture)
```

### AC6: Browser verification passes

```
Given the fix is merged into the isolated worktree stack
When the qv-browser step (S11) runs the Browser Verification Script
Then the conversation log contains a non-empty assistant bubble (not equal to "Session idle.")
And after page refresh both user and assistant bubbles re-render
And no console errors are observed
```

## Regression Prevention

The class of bug this fix addresses is **wire-protocol drift between frontend JS and backend SSE source**. Two structural changes prevent recurrence:

1. **Contract test** (S03 deliverable) — `tests/dashboard/test_chat_panel_event_protocol.py` derives its expected event set from `orch.chat.filters.INTERESTING_EVENTS`. The backend constant is already the canonical Python representation of opencode's wire vocabulary; pinning the JS listeners to it via a test means any future addition to `INTERESTING_EVENTS` (or removal) immediately surfaces as a frontend test failure rather than a silent user-visible regression.

2. **Documentation pointer** — add a one-line comment at `chat.js:187` (the listener-list literal) pointing to `orch/chat/filters.py:INTERESTING_EVENTS` so the next contributor knows where the source of truth lives.

A more ambitious follow-up (out of scope for this incident) would be to *generate* the JS listener list from the Python constant at build time, but the test-based pin is cheaper and sufficient.

## Dependencies

- **Depends on**: 88e1ed08 (committed 2026-05-17 — the model dropdown / skills tray / prompt-shape / root-path fixes). Without that commit, the user can't reach the point where this bug becomes observable.
- **Blocks**: None

## Impacted Paths

```
dashboard/static/chat_assistant/chat.js
tests/dashboard/test_chat_panel_event_protocol.py
```

## TDD Approach

**Phase 1 — RED** (must run and confirm failure before any code change):

The S03 agent writes `tests/dashboard/test_chat_panel_event_protocol.py` containing the three reproduction tests shown in **Test to Reproduce** above. The agent runs them against pre-fix `chat.js` to confirm failure, captures the failure output (the test asserts `INTERESTING_EVENTS - registered_event_names` is empty; pre-fix this set will be at least `{'message.part.updated', 'tool.execute.before', 'tool.execute.after', 'permission.asked', 'permission.replied', 'session.updated', 'session.error'}`), then either (a) waits for S01 to land its fix before re-running, or (b) writes the tests in a branch where S01 is already applied and asserts they pass.

**Important sequencing**: S01 is scheduled before S03 in the orchestrator, so by the time S03 runs the production code is already fixed. The RED evidence S03 captures MUST come from an in-test fixture (a `PRE_FIX_NAMED_EVENTS` literal that mirrors the pre-S01 array contents) and an inverted protocol check that asserts `INTERESTING_EVENTS - PRE_FIX_NAMED_EVENTS` is non-empty. Reverting `chat.js` at runtime (`git stash`, `git checkout HEAD~1`, `git show main:...`, file-copy over shipped source) is a banned anti-pattern in this project — it causes downstream QV-gate timeouts and post-S01 source must remain on disk for S05/S06/S07/S08/S09/S10/S11 to exercise.

**Phase 2 — Additional regression tests** (S03 deliverable beyond the bare reproduction):

| Test name | What it asserts |
|---|---|
| `test_chat_js_registers_every_interesting_event` | (shown above — contract test) |
| `test_chat_js_reads_properties_delta_for_streaming_text` | (shown above — payload extraction) |
| `test_chat_js_history_reads_info_and_parts` | (shown above — history reload) |
| `test_chat_js_preserves_session_storage_key` | grep-assert that `'iw-chat-session-' + _tabId` still appears (continuity invariant) |
| `test_chat_js_passes_last_event_id_on_reconnect` | grep-assert that `'last_event_id='` URL param is still appended in `_connectStream` (replay-after-blip invariant) |
| `test_chat_js_listens_for_session_idle` | regression for the only event that already worked — make sure it keeps working |
| `test_chat_js_distinguishes_properties_from_data` | assert handler tries `properties.<x>` and falls back to `data.<x>` so relay-synthesised events (`gap`, `reconnecting`) still work |

**Assertion strength rule** (per `tests/CLAUDE.md` and the I003 lesson): every test must assert a specific value or contract. `assert ".info" in body` is acceptable here because the body is a JS function source string and `.info` is the specific accessor required — but `assert len(registered) > 0` would be too weak. Reviewer must enforce this.

**Phase 3 — No browser-side unit test framework**

This project does not ship a JS unit-test runner (no Jest, Vitest, Karma — confirmed by `grep -r "test" package.json 2>/dev/null` returning nothing). End-to-end browser behaviour is covered by the qv-browser step (S11). Adding a JS test framework is out of scope for this incident.

## Notes

- **Why the comprehensive scope?** The user explicitly chose comprehensive alignment (vs. minimal "just render the deltas") so the chat panel matches the opencode SDK as a whole. This avoids a partial fix where streaming text works but tool breadcrumbs and permission modals are still broken.
- **Session continuity** is called out as a first-class user requirement; AC2 enforces it and the test suite pins the underlying invariants (sessionStorage key, `last_event_id` resumption, history shape).
- **The `INTERESTING_EVENTS` constant** at `orch/chat/filters.py:28-37` is now load-bearing: extending it (e.g., to add a new opencode event) automatically requires updating `chat.js` to satisfy `test_chat_js_registers_every_interesting_event`. This is the regression-prevention mechanism.
- **Out-of-scope follow-ups**: (a) build-time generation of the JS listener list from the Python constant; (b) richer tool-call rendering (show input/output, expandable detail); (c) reasoning-part rendering (collapsed-by-default "thinking" bubble for `ReasoningPart`). None of these are required to make the chat panel usable; all are good polish later.
- **Risk**: very low — single file change, no DB, no API, no backend. The biggest risk is breaking one of the existing flows (abort, permissions, context chip) that share the handler — explicitly mitigated by the "preserve" invariants in **Concrete event handling table** and the regression tests in Phase 2.
