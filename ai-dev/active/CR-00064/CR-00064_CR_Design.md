# CR-00064: Clear Chat History Button in AI Assistant

**Type**: Change Request
**Priority**: Medium
**Reason**: Users need a way to reset the LLM context and visible history for the active chat tab without creating a new tab — enabling a clean slate for a different topic or removal of sensitive prior context
**Created**: 2026-05-20
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item does NOT add or modify any migrations. The `opencode_session_id` column already exists on `chat_tabs`; this CR only updates its value at runtime.

## Description

The AI Assistant chat panel currently offers no way to reset the LLM conversation context. This CR adds a "Clear" button to the bottom of the composer area. When clicked, the user is shown a confirmation dialog; on confirmation, the button: creates a fresh runtime session (both OpenCode and Pi runtimes are supported), updates the `ChatTab.opencode_session_id` to the new session, clears the DOM message area, resets SSE last-eid tracking, and displays a "Chat cleared" system message. The tab's name and DB identity are preserved — only the session is replaced.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key areas: `dashboard/CLAUDE.md` (htmx/JS patterns, plain CSS rule), `dashboard/routers/chat.py` (existing tab endpoints), `orch/chat/opencode/client.py` and `orch/chat/pi/pi_runtime.py` (runtime session creation APIs).

## Current Behavior

The AI Assistant composer has three controls: a settings button (left), an Abort button, and a Send button (both right-aligned). There is no way to clear the current tab's conversation history or LLM context short of closing the tab (soft-delete) or creating a new tab. Closing the tab preserves the session ID (soft-delete invariant), so the old context is always retrievable. Users who want a genuinely fresh LLM context must create a new tab manually.

## Desired Behavior

After this CR:

1. A "Clear" button appears in the composer's Send/Abort row, to the left of the Abort button.
2. The button is **disabled** (visually dimmed) when the active tab has no message history (empty session or no session) and **enabled** when messages exist.
3. Clicking "Clear" while enabled shows a native browser confirmation: *"Clear chat history? This cannot be undone."*
4. On confirmation:
   a. The backend endpoint `POST /api/chat/tabs/{tab_id}/clear` is called.
   b. The endpoint creates a new runtime session (same runtime, model, and project directory), updates `ChatTab.opencode_session_id` to the new session ID, and resets `last_active_at`.
   c. The frontend clears the DOM message area (`_clearMessages()`).
   d. The frontend resets SSE last-eid tracking for the tab (remove the `iw-chat-last-eid-{tabId}` sessionStorage key).
   e. The frontend resets per-tab streaming/assistant state (`_tabSeenIds`, `_tabCurrentAssistantEl`, `_tabCurrentAssistantId`).
   f. A reconnect to the new session's SSE stream is opened.
   g. A "Chat cleared" info system message is displayed in the panel.
   h. The Clear button transitions back to disabled (empty history).
5. On cancellation (user clicks Cancel in the confirmation dialog), nothing changes.
6. The button is hidden (not just disabled) when no tab is active or the panel is in the no-tabs empty state.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `dashboard/templates/chat_assistant/composer.html` | 3 controls: settings, abort, send | 4 controls: settings, clear, abort, send |
| `dashboard/static/chat_assistant/chat.js` | No clear button logic | New `_clearChat()` function; button enabled/disabled state tracking; `_tabHasHistory[tabId]` flag |
| `dashboard/static/chat_assistant/chat.css` | No clear button styles | New `#chat-assistant-clear` disabled state rule (plain CSS, not Tailwind) |
| `dashboard/routers/chat.py` | No clear endpoint | New `POST /api/chat/tabs/{tab_id}/clear` endpoint |
| `tests/dashboard/test_chat_router.py` | Tests existing tab endpoints | New test for the clear endpoint |
| `tests/dashboard/test_chat_clear_button.py` (new) | Does not exist | Tests clear button presence, enabled/disabled logic, and JS wiring |

### Breaking Changes

- None. New endpoint is additive. Existing endpoints unchanged.

### Data Migration

- None required. `opencode_session_id` is updated by the new endpoint at runtime, not via a migration.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | api-impl | New `POST /api/chat/tabs/{tab_id}/clear` backend endpoint | — |
| S02 | frontend-impl | Clear button in `composer.html` + full JS wiring | After S01 |
| S03 | code-review-impl | Review S01 + S02 | — |
| S04 | code-review-fix-impl | Fix CRITICAL/HIGH findings | — |
| S05 | code-review-final-impl | Cross-agent final review | — |
| S06 | code-review-fix-final-impl | Fix final findings | — |
| S07 | qv-gate (lint) | `make lint` | — |
| S08 | qv-gate (tests) | `uv run pytest tests/dashboard/ -k "chat"` | — |
| S09 | qv-browser | Browser verification | — |
| S10 | self-assess-impl | Self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None (runtime value update only via existing `update_tab` service)
- **Migration notes**: N/A

### API Changes

- **New endpoints**: `POST /api/chat/tabs/{tab_id}/clear`
  - Request body: none (tab ID in path is sufficient; runtime/model/directory resolved from the tab row)
  - Response: `{"tab": {tab_dict}}` on success with the updated tab (new `opencode_session_id`)
  - Errors: `404` if tab not found, `503` if runtime unavailable, `400` if tab has no session to clear
  - Health-gated: same pattern as `POST /api/chat/tabs/{tab_id}/prompt`
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **Modified components**:
  - `dashboard/templates/chat_assistant/composer.html` — add `<button id="chat-assistant-clear">` between settings and abort buttons
  - `dashboard/static/chat_assistant/chat.js` — add `_clearChat()`, `_tabHasHistory`, `_updateClearButton()`, wire event listener
  - `dashboard/static/chat_assistant/chat.css` — add disabled state opacity for `#chat-assistant-clear`
- **New components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00064_CR_Design.md` | Design | This document |
| `CR-00064_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00064_S01_API_prompt.md` | Prompt | S01 — new clear endpoint |
| `prompts/CR-00064_S02_Frontend_prompt.md` | Prompt | S02 — clear button UI + JS |
| `prompts/CR-00064_S03_CodeReview_prompt.md` | Prompt | S03 — per-agent code review |
| `prompts/CR-00064_S04_CodeReview_FIX_prompt.md` | Prompt | S04 — fix CRITICAL/HIGH findings |
| `prompts/CR-00064_S05_CodeReview_Final_prompt.md` | Prompt | S05 — final cross-agent review |
| `prompts/CR-00064_S06_CodeReview_FIX_Final_prompt.md` | Prompt | S06 — fix final findings |
| `prompts/CR-00064_S07_Lint_prompt.md` | Auxiliary | S07 lint reference (not used by orchestrator — qv-gate steps execute via `command` field in manifest) |
| `prompts/CR-00064_S09_BrowserVerification_prompt.md` | Prompt | S09 — browser verification |
| `prompts/CR-00064_S10_SelfAssess_prompt.md` | Prompt | S10 — self-assessment |

## Acceptance Criteria

### AC1: Clear button visible and correctly enabled/disabled

```
Given the AI Assistant panel is open on an active tab
When the tab has no message history (brand new or freshly cleared)
Then the Clear button is visible but disabled (dimmed, not interactive)

Given the AI Assistant panel is open on an active tab
When the tab has one or more messages in the chat window
Then the Clear button is enabled (full opacity, interactive)
```

### AC2: Confirmation dialog shown before clearing

```
Given the Clear button is enabled
When the user clicks Clear
Then a confirmation dialog appears with text "Clear chat history? This cannot be undone."
And if the user cancels, no changes are made to the tab or the message history
```

### AC3: Full clear executes on confirmation

```
Given the user confirms the clear dialog
When the POST /api/chat/tabs/{tab_id}/clear request succeeds
Then the DOM message area is empty
And a "Chat cleared" info system message is displayed
And the Clear button is disabled (no history)
And the LLM context is fresh (subsequent prompts have no memory of prior messages)
```

### AC4: Works for both OpenCode and Pi runtimes

```
Given a chat tab using the Pi runtime
When the user clears the chat
Then a new Pi session is created and the tab's session ID is updated
And the chat panel behaves identically to an OpenCode tab clear
```

### AC5: SSE stream reconnects to new session after clear

```
Given the user has confirmed the clear
When the clear completes
Then the EventSource is reconnected to the new session's stream
And the last-eid sessionStorage key for this tab is cleared
So that the new session starts streaming from event 0
```

## Rollback Plan

- **Database**: N/A — no schema changes. If a clear was accidentally triggered, the old session still exists in the runtime; only the `opencode_session_id` pointer in the DB was changed. A manual `UPDATE chat_tabs SET opencode_session_id = '<old_sid>' WHERE id = '<tab_id>'` can restore the pointer, though runtime session availability depends on uptime.
- **Code**: Revert the commit. No data is lost; the new sessions created by `clear` are orphaned but harmless in the runtime.
- **Data**: No data loss risk in the orchestration DB schema.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/routers/chat.py`
- `dashboard/templates/chat_assistant/composer.html`
- `dashboard/static/chat_assistant/chat.js`
- `dashboard/static/chat_assistant/chat.css`
- `tests/dashboard/test_chat_router.py`
- `tests/dashboard/test_chat_clear_button.py`

## TDD Approach

- **Unit tests** (`tests/dashboard/test_chat_clear_button.py` — new):
  - JS source assertions (regex/grep-based, matching existing chat test patterns): `_clearChat` function exists; `chat-assistant-clear` button ID referenced; `_tabHasHistory` variable used; `_updateClearButton` function exists; `POST .*/clear` URL pattern present.
- **Integration tests** (`tests/dashboard/test_chat_router.py` — add cases):
  - `POST /api/chat/tabs/{tab_id}/clear` returns 200 with updated tab when runtime is healthy.
  - Returns 404 for unknown tab ID.
  - Returns 400 when tab has no `opencode_session_id` (nothing to clear).
  - Returns 503 when runtime is unavailable.
- **Updated tests**: `tests/dashboard/test_chat_templates.py` — verify `chat-assistant-clear` button is present in the rendered composer template.

## Notes

- Use native `window.confirm()` for the confirmation dialog — no custom modal needed. This avoids template complexity and keeps the implementation minimal.
- The `_tabHasHistory[tabId]` flag must be set to `true` in `_loadTabHistory` when at least one message is rendered, and when the first message part arrives via SSE. It must be reset to `false` on tab close, on new-tab creation with no session, and after a successful clear.
- The `POST /api/chat/tabs/{tab_id}/clear` endpoint should close the old SSE relay for the tab before creating the new session, to avoid the old relay emitting events into the new session's stream. Check if `_relay_manager` has a `close_relay(sid)` or equivalent before creating the new session.
- ES5 only in JS — no arrow functions, no `const`/`let`.
- Plain CSS for the disabled button state — append to `dashboard/static/chat_assistant/chat.css`, not via Tailwind `make css`.
