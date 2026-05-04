# F-00077_S10_CodeReview_Frontend_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step Being Reviewed**: S08 (frontend-impl)
**Review Step**: S10

---

## ⛔ Docker / Migrations off-limits

Same constraints. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md`
- `ai-dev/active/F-00077/reports/F-00077_S08_Frontend_report.md`
- All files in S08's `files_changed`

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S10_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations → CRITICAL.

## Review Checklist

### 1. Behavior Compliance

- `composer.js` no longer sends `conversation_history` (verify the line `conversationHistory = []` is gone; verify the body object has `conversation_id` but NOT `conversation_history`).
- The `meta` event is captured by stream.js and forwarded to `onMeta`. CRITICAL if dropped — the client never learns the conversation_id otherwise.
- The "New chat" button id is `chat-new-btn` (matches what panel.js expects to bind).
- Replay-on-open fires when collapsed→expanded AND on initial page load if the previous panel state was expanded. Verify both code paths.

### 2. localStorage Resilience

- ALL `localStorage` access is wrapped in try/catch. Inspect every call site. CRITICAL if any throw can escape (incognito mode would crash the chat panel).
- The TTL check (`Date.now() - last_active_at > 4*60*60*1000`) is the SOLE rotation mechanism. Reading a stale entry returns null (not the stale id).
- Clear-on-"New chat" is correct — the localStorage row is removed, NOT just emptied.

### 3. Code Quality

- No new global functions; new helpers attach to `window.iwChatState` (or an equivalent namespace, consistent with `window.iwChat` and `window.iwChat.streamAnswer`). Module pollution is a HIGH finding.
- DOM event listeners use `addEventListener` (NOT `onclick=` attributes).
- No inline styles; only Tailwind utility classes.
- The replay rendering reuses `appendUserBubble` / `createAssistantRenderer` — does NOT reimplement the bubble HTML.

### 4. Accessibility

- "New chat" button has `aria-label="Start a new chat (clears history)"` (or equivalent).
- Empty-state announcement after "New chat" reuses the existing live region OR adds a `role="status"` element. Verify keyboard users get feedback.
- Focus management: clicking "New chat" doesn't strand focus on a removed message; ideally focus moves to the composer textarea.

### 5. CSS / Tailwind

- `make css` was run; `dashboard/static/styles.css` diff was committed.
- No new utility classes that weren't already in the JIT scan path (CRITICAL — silent UI regression otherwise).

### 6. Project Conventions

- Vanilla JS (no jQuery / framework).
- Function-style imports (no `import` syntax — match existing files).
- File ordering: helpers at top, event handlers below, namespace assignment at end.

### 7. Testing

- Snapshot-style test verifies the `chat-new-btn` is present in the rendered HTML.
- TTL test (if a JS runner is configured) covers the "stale entry returns null" branch.
- localStorage-throws test (incognito-mode simulation) covers the graceful-no-op branch.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
make test-frontend       # if the project has it; otherwise the python-side rendering test
```

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | conversation_history still sent, meta event dropped, localStorage exception escapes, missing make css | Must fix |
| HIGH | Aria-label missing, focus management broken, global pollution | Must fix |
| MEDIUM (fixable) | Style drift, missing event listener cleanup | Fix in fix cycle |

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-impl",
  "work_item": "F-00077",
  "step_reviewed": "S08",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
