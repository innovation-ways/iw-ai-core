# CR-00064_S03_CodeReview_prompt

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant
**Step Being Reviewed**: S01 (api-impl) + S02 (frontend-impl)
**Review Step**: S03

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00064 --json`
- `ai-dev/active/CR-00064/CR-00064_CR_Design.md` — Design document
- `ai-dev/active/CR-00064/reports/CR-00064_S01_API_report.md`
- `ai-dev/active/CR-00064/reports/CR-00064_S02_Frontend_report.md`
- All files listed in both reports' `files_changed`

## Output Files

- `ai-dev/active/CR-00064/reports/CR-00064_S03_CodeReview_report.md`

## Context

You are reviewing both the API implementation (S01) and frontend implementation (S02) for CR-00064 — the Clear Chat History button.

## Read the Design Document FIRST

Read all `## Acceptance Criteria` and `## TDD Approach` sections. Verify all 5 ACs are implemented.

Key checks:
- AC1: Clear button visible with correct enabled/disabled state — `_tabHasHistory` tracking wired?
- AC2: `window.confirm()` called before any destructive action?
- AC3: Full clear pipeline: API call → DOM clear → "Chat cleared" message → button disabled?
- AC4: Pi runtime path in the `clear` endpoint works?
- AC5: SSE reconnects to new session; old `last-eid` removed from sessionStorage?
- TDD: `test_chat_clear_button.py` and new `test_chat_router.py` cases in `files_changed`?

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Flag any new violations as CRITICAL.

## Review Checklist

### 1. Architecture Compliance

- Backend endpoint follows thin-router pattern (no business logic that belongs in service layer).
- Async `def` used for the route (all chat routes are async).
- Frontend uses ES5 only — no arrow functions, no `const`/`let`.
- Plain CSS for the disabled button state, not Tailwind.

### 2. Code Quality — API

- `POST /api/chat/tabs/{tab_id}/clear` handles all four cases: 200 (success), 404 (tab not found), 400 (no session), 503 (runtime unavailable).
- Old relay closed before new session created (or documented as intentionally skipped if no `close` method exists).
- `db.commit()` called exactly once after the update.
- Response shape is `{"tab": _tab_to_dict(tab)}` matching other tab endpoints.

### 3. Code Quality — Frontend

- `_clearChat()` checks `_tabHasHistory[_activeTabId]` before calling `window.confirm` — no spurious confirm dialogs on empty tabs.
- After successful clear: `_tabEs[tabId]` closed + deleted, `sessionStorage.removeItem('iw-chat-last-eid-' + tabId)` called, `_tabSeenIds[tabId]` deleted, `_connectStream(tabId)` called to open new stream.
- `_updateClearButton()` called in the same places as `_updateSendAbortButtons()`.
- `_tabHasHistory[tabId]` set to `true` in both `_loadTabHistory` (after rendering ≥1 message) and in the SSE event handler (on first delta/part event).
- `_tabHasHistory[tabId]` reset to `false` in `_clearMessages()` and in `_clearChat()` on success.

### 4. Security

- No XSS in the "Chat cleared" system message — uses the existing `_appendSystemMessage` helper.
- No new endpoints that bypass auth/authorization (the clear endpoint should be protected by the same session/auth as other tab endpoints — verify this matches the project's auth model).

### 5. Testing

- `tests/dashboard/test_chat_clear_button.py` present in S02's `files_changed` with ≥8 test cases.
- 4 new test cases in `test_chat_router.py` present in S01's `files_changed`.
- `test_chat_templates.py` updated if composer template changed.
- TDD RED evidence present and plausible in both S01 and S02 reports.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_chat_clear_button.py tests/dashboard/test_chat_router.py -v --no-header
```

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview",
  "work_item": "CR-00064",
  "step_reviewed": "S01+S02",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
