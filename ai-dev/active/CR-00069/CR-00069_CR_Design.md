# CR-00069: AI Assistant — Remove Clear Button Confirmation Dialog

**Type**: Change Request
**Priority**: Low
**Reason**: UX friction removal — the Clear button is already disabled when there is no chat history, so the confirmation popup is an unnecessary extra click for a cheap, low-risk action.
**Created**: 2026-05-20
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This CR adds no Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** migrations — it is a frontend-only change.

## Description

Clicking the AI Assistant "Clear" button currently opens a native `window.confirm` popup before clearing the chat. This CR removes that popup so a click clears the chat immediately. The existing "Chat cleared." system message remains as the only feedback.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Relevant: the AI Assistant's Clear behaviour is the `_clearChat()` function in `dashboard/static/chat_assistant/chat.js`; the button itself is in `dashboard/templates/chat_assistant/composer.html`. An existing dashboard test, `tests/dashboard/test_chat_clear_button.py`, asserts on the Clear behaviour.

## Current Behavior

The Clear button (`#chat-assistant-clear` in `composer.html`) is wired to `_clearChat()` in `chat.js`. `_clearChat()` first guards on `_activeTabId` and `_tabHasHistory[_activeTabId]`, then calls:

```
if (!window.confirm('Clear chat history? This cannot be undone.')) return;
```

If the user dismisses the dialog, the function returns and nothing happens. If confirmed, it POSTs to `/api/chat/tabs/{id}/clear`, resets SSE/streaming state, clears the DOM, disables the Clear button, appends a "Chat cleared." system message, and reconnects the stream.

The button is already rendered `disabled` and is only enabled when the active tab has history (`_updateClearButton()`), so the confirmation is the only thing standing between a click and a clear.

An existing test, `tests/dashboard/test_chat_clear_button.py::test_clear_calls_confirm`, asserts that the string `window.confirm` is present in `chat.js` and enforces "must show a confirmation dialog via window.confirm before clearing history".

## Desired Behavior

- Clicking the Clear button (when enabled) clears the chat **immediately**, with no `window.confirm` popup and no other confirmation UI.
- The existing guards remain: `_clearChat()` still returns early if there is no active tab or the active tab has no history; the button stays `disabled` when there is no history.
- All post-clear behaviour is unchanged: the `/api/chat/tabs/{id}/clear` POST, SSE/streaming reset, DOM clear, button-state update, stream reconnect, and the "Chat cleared." system message.
- The existing test that enforces the presence of the confirmation dialog is inverted so it asserts the dialog is **absent** — i.e. `_clearChat()` no longer references `window.confirm`.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `chat_assistant/chat.js` — `_clearChat()` | Calls `window.confirm(...)` and returns early if dismissed | The `window.confirm` line is removed; the clear proceeds directly after the existing guards |
| `tests/dashboard/test_chat_clear_button.py` | `test_clear_calls_confirm` asserts `window.confirm` IS present | Test inverted to assert `window.confirm` is NOT present in `_clearChat()` |

### Breaking Changes

- None. No API contract, DB schema, or behaviour outside the AI Assistant Clear flow changes. Behaviourally, the only difference is the absence of the confirmation prompt.

### Data Migration

- None. No schema or data changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | Remove the `window.confirm` line from `_clearChat()`; invert the `test_clear_calls_confirm` test | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | code-review-fix-impl | Fix CRITICAL/HIGH/MEDIUM_FIXABLE findings | — |
| S04 | code-review-final-impl | Cross-agent final review | — |
| S05 | code-review-fix-final-impl | Fix final review findings | — |
| S06 | qv-gate | `make test-integration` (runs `tests/dashboard/` — includes the inverted test) | — |
| S07 | qv-browser | Browser verification — Clear works with no popup | — |
| S08 | self-assess-impl | Post-execution self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None — `POST /api/chat/tabs/{id}/clear` is unchanged
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: `chat_assistant/chat.js` (`_clearChat()`)
- **Removed components**: The `window.confirm` confirmation step inside `_clearChat()`

## File Manifest

All files for this work item live under `ai-dev/active/CR-00069/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00069_CR_Design.md` | Design | This document |
| `CR-00069_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00069_S01_Frontend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00069_S02_CodeReview_prompt.md` | Prompt | S02 code review instructions |
| `prompts/CR-00069_S03_CodeReviewFix_prompt.md` | Prompt | S03 review-fix instructions |
| `prompts/CR-00069_S04_CodeReviewFinal_prompt.md` | Prompt | S04 final review instructions |
| `prompts/CR-00069_S05_CodeReviewFixFinal_prompt.md` | Prompt | S05 final review-fix instructions |
| `prompts/CR-00069_S07_BrowserVerification_prompt.md` | Prompt | S07 browser verification instructions |
| `prompts/CR-00069_S08_SelfAssess_prompt.md` | Prompt | S08 self-assessment instructions |

Reports are created during execution in `ai-dev/work/CR-00069/reports/`.

## Acceptance Criteria

### AC1: Clear button clears immediately with no popup

```
Given the AI Assistant panel is open with an active chat tab that has chat history
When the user clicks the "Clear" button
Then the chat is cleared immediately with no window.confirm popup shown
```

### AC2: Post-clear behaviour is unchanged

```
Given the user has clicked the "Clear" button on a tab with history
When the clear completes
Then the messages are removed, the Clear button becomes disabled, and a "Chat cleared." system message is shown
```

### AC3: Empty-chat guard still holds

```
Given the AI Assistant panel is open with an active chat tab that has no chat history
When the panel renders
Then the "Clear" button is disabled and clicking it does nothing
```

### AC4: The clear-button test enforces the absence of the dialog

```
Given the dashboard test suite
When test_chat_clear_button.py runs
Then it asserts _clearChat() does NOT reference window.confirm, and the suite passes
```

## Rollback Plan

- **Database**: Not applicable — no schema changes.
- **Code**: Revert the squash-merge commit for CR-00069. `chat.js` and `test_chat_clear_button.py` return to their prior state, restoring the confirmation dialog.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/static/chat_assistant/chat.js`
- `tests/dashboard/test_chat_clear_button.py`
- `tests/dashboard/**`

## TDD Approach

- Unit tests: None required — pure presentation change with no Python logic.
- Integration tests: None required — the API endpoint is unchanged.
- Updated tests: `tests/dashboard/test_chat_clear_button.py::test_clear_calls_confirm` must be inverted — rename it (e.g. `test_clear_has_no_confirm`) and change the assertion to require `window.confirm` is NOT present in the `_clearChat()` body. Update the file's module docstring numbered list to match. The other tests in that file (function exists, calls API, removes eid, button disabled-by-default) remain unchanged and must still pass.
- Browser verification (S07): confirms clicking Clear clears the chat with no popup and the "Chat cleared." message appears.

## Notes

- This is effectively a one-line removal in `chat.js` plus a one-test inversion. Keep the change minimal — do NOT alter the guards, the API call, or any post-clear logic.
- `make test-integration` runs `tests/integration/ tests/dashboard/` (per the Makefile), so the inverted test is exercised by the S06 QV gate.
- The native `window.confirm` dialog cannot be meaningfully screenshotted for pre-evidence; the pre-state evidence is a panel screenshot showing the Clear button.
