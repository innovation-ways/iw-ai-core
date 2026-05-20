# CR-00063: Restore Chat Message History on Browser Reload

**Type**: Change Request
**Priority**: High
**Reason**: UX bug — chat panel renders empty on browser restart even though the runtime session holds full conversation history, causing users to repeat questions or lose context
**Created**: 2026-05-20
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item does NOT add, modify, or require any migrations. Frontend-only change.

## Description

When a user closes and reopens their browser, the AI Assistant chat panel shows an empty message window even though the runtime session (OpenCode or Pi) still holds the full conversation history. The `_loadTabHistory()` function is called correctly but only renders user and assistant text messages — tool call and tool result messages are silently skipped, and the function suppresses all errors. A secondary issue is that the `last_active_at` DB timestamp is not used as a fallback when sessionStorage is cleared on browser restart, though the current fallback to `_tabs[0].id` already works in most cases.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key areas for this CR: `dashboard/CLAUDE.md` (htmx/JS patterns, plain CSS rule), `dashboard/static/chat_assistant/chat.js` (2,256-line frontend module).

## Current Behavior

When the user closes the browser and reopens it:

1. sessionStorage is cleared (browser close wipes session-scoped storage).
2. `_bootstrapTabs()` fetches the tab list from the API, falls back to `_tabs[0].id` because `lastActive` is null, and calls `_activateTab(tabId)`.
3. `_activateTab` calls `_clearMessages()` then `_loadTabHistory(tabId)`.
4. `_loadTabHistory` fetches `GET /api/chat/tabs/{tab_id}` which returns the full message list from the runtime session.
5. **Only user and assistant text messages are rendered** (lines 1688–1692 in chat.js). Messages whose role is anything else — tool calls, tool results, function calls — are silently skipped. Additionally, if an assistant message contains only tool-use parts (no text part), its text is rendered as an empty string, creating an empty bubble or no visible output.
6. **All errors are silently swallowed** (`.catch(function () { /* silently ignore */ })` at line 1698). If the runtime is temporarily unhealthy at page load time, the fetch fails and the chat stays empty with no indication to the user.
7. The LLM context IS intact (the runtime session has the full history), so continued conversation produces correct answers — the problem is purely visual.

## Desired Behavior

After this CR:

1. On browser restart (or any page reload), the full message history is rendered in the chat panel for the active tab.
2. All message types are rendered:
   - User messages → right-aligned blue bubble (existing `_appendUserMessage`)
   - Assistant text messages → left-aligned bubble (existing `_appendOrUpdateAssistantMessage`)
   - Tool call messages → gray bordered tool-call box (existing `_appendToolCall`)
   - Tool result messages → gray bordered tool-result box (existing `_appendToolResult`)
3. If `_loadTabHistory` encounters a network or runtime error, a system error message is shown in the chat panel instead of silently failing.
4. On fresh page load (sessionStorage cleared), the tab with the most recent `last_active_at` timestamp (from the API response) is activated, providing better cross-browser and multi-tab consistency.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `dashboard/static/chat_assistant/chat.js:_loadTabHistory` | Renders only user+assistant text messages; silently swallows errors | Renders all message types; shows error system message on failure |
| `dashboard/static/chat_assistant/chat.js:_bootstrapTabs` | Falls back to `_tabs[0]` when sessionStorage is empty | Falls back to tab with highest `last_active_at` from the API list |
| `tests/dashboard/test_chat_panel_event_protocol.py` | Checks `_loadTabHistory` function exists | May need update if function signature changes |
| `tests/dashboard/test_chat_history_restore.py` (new) | Does not exist | New test verifying tool call/result rendering and error handling |

### Breaking Changes

- None. All changes are additive or bug-fix-only. Existing rendering helpers (`_appendToolCall`, `_appendToolResult`) are already present.

### Data Migration

- None required. No schema changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | Fix `_loadTabHistory` rendering + error handling; fix `_bootstrapTabs` fallback | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | code-review-fix-impl | Fix CRITICAL/HIGH findings from S02 | — |
| S04 | code-review-final-impl | Cross-agent final review | — |
| S05 | code-review-fix-final-impl | Fix final findings | — |
| S06 | qv-gate (lint) | `make lint` | — |
| S07 | qv-browser | Browser verification — history renders after reload | — |
| S08 | self-assess-impl | Self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **Modified components**:
  - `dashboard/static/chat_assistant/chat.js` — `_loadTabHistory` and `_bootstrapTabs` functions
- **New components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00063_CR_Design.md` | Design | This document |
| `CR-00063_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00063_S01_Frontend_prompt.md` | Prompt | S01 — fix history rendering in chat.js |
| `prompts/CR-00063_S02_CodeReview_prompt.md` | Prompt | S02 — per-agent code review |
| `prompts/CR-00063_S03_CodeReview_FIX_prompt.md` | Prompt | S03 — fix CRITICAL/HIGH findings |
| `prompts/CR-00063_S04_CodeReview_Final_prompt.md` | Prompt | S04 — final cross-agent review |
| `prompts/CR-00063_S05_CodeReview_FIX_Final_prompt.md` | Prompt | S05 — fix final findings |
| `prompts/CR-00063_S06_Lint_prompt.md` | Prompt | S06 — lint QV gate |
| `prompts/CR-00063_S07_BrowserVerification_prompt.md` | Prompt | S07 — browser verification |
| `prompts/CR-00063_S08_SelfAssess_prompt.md` | Prompt | S08 — self-assessment |

## Acceptance Criteria

### AC1: All message types rendered on history load

```
Given a chat tab has a runtime session containing user messages, assistant messages,
      tool call messages, and tool result messages
When the user opens the AI Assistant panel (on page load or browser restart)
Then all message types are visible in the chat window in chronological order:
     user bubbles, assistant bubbles, tool call boxes, and tool result boxes
```

### AC2: Error shown when history load fails

```
Given the runtime is temporarily unavailable when the page loads
When _loadTabHistory fetches GET /api/chat/tabs/{tab_id} and receives a non-200 response
Then a system error message is displayed in the chat panel (e.g., "Could not load
     chat history — runtime unavailable")
And the error is NOT silently swallowed
```

### AC3: Best-match tab restored on fresh page load

```
Given multiple chat tabs exist and sessionStorage has been cleared (browser restart)
When _bootstrapTabs runs and lastActive sessionStorage key is absent
Then the tab with the most recent last_active_at timestamp is activated
     (instead of always falling back to array index 0)
```

### AC4: History renders correctly for text-only conversations

```
Given a chat tab has a conversation with only user + assistant text exchanges
     (no tool calls)
When the user reloads the page
Then all user messages and assistant messages are visible in the chat window
```

## Rollback Plan

- **Database**: N/A — no schema changes
- **Code**: Revert the commit that applied the frontend-impl changes. No data is affected.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/static/chat_assistant/chat.js`
- `dashboard/static/chat_assistant/chat.css`
- `tests/dashboard/test_chat_panel_event_protocol.py`
- `tests/dashboard/test_chat_history_restore.py`

## TDD Approach

- **Unit tests**: New test file `tests/dashboard/test_chat_history_restore.py` — verify that `chat.js` contains the correct rendering logic for tool call/result message parts (regex/grep-based assertions on the JS source, consistent with existing chat test patterns).
- **Integration tests**: Verify `GET /api/chat/tabs/{tab_id}` returns correct `messages` shape with all part types — already covered by `test_chat_router.py`; add assertions for tool_use and tool_result parts if not present.
- **Updated tests**: `tests/dashboard/test_chat_panel_event_protocol.py` — may need updating if the `_loadTabHistory` function signature or internal structure changes materially.

## Notes

- The `_appendToolCall` and `_appendToolResult` helpers already exist in `chat.js` (used for live streaming). The fix in `_loadTabHistory` must reuse these existing helpers rather than duplicating rendering logic.
- The Pi runtime and OpenCode runtime use different message schemas. The implementation must handle both. In OpenCode, tool call parts have `type: "tool-use"` or `type: "tool_use"`; verify the exact type strings from `orch/chat/opencode/client.py` and `orch/chat/pi/pi_runtime.py` before hardcoding.
- The `.catch(function () { /* silently ignore */ })` in `_loadTabHistory` was likely defensive programming to avoid breaking the panel. The fix must replace it with a user-visible error system message using the existing `_appendSystemMessage(text, 'error')` helper.
- `make lint` covers `scripts/check_templates.py` for Jinja2 format-filter checks and `ruff` for Python. The JS check is via `node --check` on dashboard JS. Ensure no new lint violations are introduced.
