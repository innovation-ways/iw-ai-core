# I-00087 S02 Code Review Report

**Step reviewed**: S01 (frontend-impl)
**Reviewer**: code-review-impl
**Date**: 2026-05-17 (re-confirmed by independent S02 pass — verdict unchanged)

---

## Summary

S01 rewrote three sections of `dashboard/static/chat_assistant/chat.js` to align with the opencode 1.15 wire protocol. The implementation is largely correct and solves the primary defects described in the design document. All quality gates pass and all 52 existing tests continue to pass.

One HIGH finding (confirmed on re-review): `_loadHistory` leaves `_currentAssistantEl` set after rendering history messages, causing subsequent streaming text from a new prompt to be appended to the last history bubble rather than creating a new one. This breaks AC1 ("an assistant message bubble is created on first delta") for any session with prior assistant history — which covers the primary use-case this fix enables.

**Verdict: FAIL** (1 HIGH finding).

---

## Quality Gates

### Pre-review lint & format (NON-NEGOTIABLE)

```
make lint      → All checks passed (ruff + node --check + check_templates.py)
make format-check → 742 files already formatted
```

No new violations. `node --check dashboard/static/chat_assistant/chat.js` passes — no JS syntax errors. ✓

### Existing chat tests

```
uv run pytest tests/dashboard/test_chat_router.py tests/unit/test_chat_client.py -v --no-cov
52 passed, 0 failed
```

No regression in router/client coverage. ✓

---

## Review Checklist Results

### 1. Wire-protocol alignment ✓

**namedEvents array (lines 186–210):**

All 8 events in `INTERESTING_EVENTS` are present in `namedEvents`:
`message.part.updated`, `tool.execute.before`, `tool.execute.after`, `permission.asked`, `permission.replied`, `session.idle`, `session.updated`, `session.error`. ✓

Relay-synthesised events (`gap`, `reconnecting`, `error`) preserved. `relay.error` added as well. ✓

Comment at line 186 pointing to `orch/chat/filters.py INTERESTING_EVENTS` as source of truth. ✓

**`_handleEvent` per-event checks:**

- `message.part.updated` (lines 294–309): reads `props.delta` AND `props.part.text`. ✓
- `message.updated` (lines 319–340): reads `props.info`, checks `info.role`, `info.time.completed`, `info.error`. All three branches present. ✓
- `tool.execute.before` (lines 349–354): renders `_appendToolCall(toolName, {})` — visible breadcrumb. AC3 satisfied. ✓
- `tool.execute.after` (lines 356–360): marks complete via `_appendToolResult`. ✓
- `permission.asked` (lines 363–371): reads `props.id || props.request_id`, calls `_showApprovalModal`. Modal fires. ✓

  Note: Design table mentions `permission.updated` as the wire name, but S01 correctly resolved the inconsistency in favour of the SDK types and `INTERESTING_EVENTS` (both use `permission.asked`). This is the right call.

- `permission.replied` (lines 374–379): dismisses modal. ✓
- `_replyPermission` URL resolves to `/api/chat/sessions/{sid}/permissions/{rid}`. ✓
- `session.idle` (lines 381–396): preserved including `permission_denied`/`aborted` sub-cases via `props || data` fallback. ✓

### 2. History reload ✓ (with one finding)

`_loadHistory` (lines 625–657):
- Iterates `data.messages`. ✓
- Reads `entry.info` (not `m.role` directly). ✓
- Extracts text via `parts.filter(p => p.type === 'text').map(p => p.text).join('')`. Multi-part messages handled correctly — not `parts[0].text`. ✓
- Passes `info.id` as dedup key for assistant messages (line 652). ✓

**See finding F-001 below.**

### 3. Session-continuity invariants ✓

S01's grep audit is correct. Verified directly against the file:

1. `'iw-chat-session-' + _tabId` — lines 107, 117, 135, 160. ✓
2. `last_event_id=` — line 174. ✓
3. `_loadHistory(` — lines 118, 139. ✓
4. `sessionStorage.removeItem` — line 107. ✓
5. `switchSession` — line 111, exported at line 130. ✓
6. `_renderChip` — lines 83, 89, 660. ✓

All six invariants preserved.

### 4. Code Quality ✓

- Payload asymmetry comment at top of `_handleEvent` (lines 229–237). ✓
- `namedEvents` comment pointing to `orch/chat/filters.py:INTERESTING_EVENTS` (lines 186–188). ✓
- No new dependencies — vanilla JS, matches existing file style. ✓

### 5. Project Conventions ✓

- No `navigator.clipboard.writeText` calls anywhere in the file. ✓
- No new Tailwind classes added in JS (templates not touched). ✓

### 5a. TDD RED Evidence

S01 correctly did not write tests — that is S03's responsibility. The S01 report shows 52 existing tests passing, not new test authorship. This is correct behaviour.

The report does not have an explicit `tdd_red_evidence: "n/a — ..."` field as the review prompt specified to check. The existing "Test Results" section adequately conveys the same information. Not penalised — S03 will be held to this standard.

### 6. Security ✓

- No hardcoded credentials or session IDs. ✓
- No `eval()`. ✓
- All tool-name and user-provided content routed through `_escHtml` before `innerHTML` insertion:
  - `_appendToolCall`: `_escHtml(toolName)` at line 579. ✓
  - `_appendToolResult`: `_escHtml(resultStr)` at line 592. ✓
  - `_showApprovalModal`: `_escHtml` for toolName, argsStr, rationale at lines 457–463. ✓
  - Streaming assistant text: `textContent` assignment (line 554 and line 539), not innerHTML. ✓

### 7. Testing

S01 does not write tests — see §5a above. No penalty.

---

## Findings

### F-001 — HIGH: `_loadHistory` leaves `_currentAssistantEl` set, causing next streaming response to append to last history bubble

**Severity**: HIGH  
**Category**: code_quality  
**File**: `dashboard/static/chat_assistant/chat.js`  
**Line**: 534 (accumulation guard in `_appendOrUpdateAssistantMessage`) / 654 (end of `forEach` in `_loadHistory`)

**Description**:

`_loadHistory` calls `_appendOrUpdateAssistantMessage(info.id, text, true)` for each assistant message in history. That call (with `isFinal=true`) bypasses the accumulation branch and creates a new DOM element, but at the end also sets `_currentAssistantEl = wrap` and `_currentAssistantId = info.id`.

After `_loadHistory` finishes, `_currentAssistantEl` points to the last assistant history bubble. When the user sends a new prompt and the first `message.part.updated` or `message.part.delta` arrives (with `isFinal=false`), the accumulation check:

```js
if (!isFinal && _currentAssistantEl && _currentAssistantId !== null) {
```

evaluates to `true`, and the new streaming text is appended to the stale history element rather than creating a new bubble. AC1 requires "an assistant message bubble is created on first delta" — this fails when prior history exists.

The bug is not present for first-ever conversations (no history = `_currentAssistantEl` is null), but is reliably triggered when continuing any session that had an assistant reply.

**Suggestion**:

Add two lines after the `forEach` loop in `_loadHistory`:

```js
data.messages.forEach(function (entry) {
  // ... existing code ...
});
// Reset so streaming text for the next prompt creates a new bubble, not appending to history.
_currentAssistantEl = null;
_currentAssistantId = null;
```

---

## Review Result

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00087",
  "step_reviewed": "S01",
  "verdict": "fail",
  "findings": [
    {
      "severity": "HIGH",
      "category": "code_quality",
      "file": "dashboard/static/chat_assistant/chat.js",
      "line": 534,
      "description": "_loadHistory sets _currentAssistantEl to the last history assistant bubble and _currentAssistantId to its message ID. The accumulation guard at line 534 (`!isFinal && _currentAssistantEl && _currentAssistantId !== null`) does NOT compare the incoming eid against _currentAssistantId. After a page reload with prior history, the first streaming chunk of a new prompt (different messageID) satisfies the guard and is appended to the stale historical bubble. AC1 ('an assistant message bubble is created on first delta') fails for any session with prior assistant history — the most common post-fix scenario.",
      "suggestion": "Either (a) add two lines after the forEach loop in _loadHistory: `_currentAssistantEl = null; _currentAssistantId = null;` — or (b) strengthen the accumulation guard: `if (!isFinal && _currentAssistantEl && _currentAssistantId !== null && eid === _currentAssistantId)`. Option (a) is simpler and sufficient."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "52 passed, 0 failed",
  "notes": "All wire-protocol alignment, history reload, session-continuity invariants, security, and code quality checks pass. Single HIGH: stale _currentAssistantEl after _loadHistory breaks AC1 for returning users. Fix is trivial (two lines). All 8 INTERESTING_EVENTS registered. Permission flow (permission.asked, correct SDK key), tool breadcrumbs, _escHtml in every innerHTML path, and relay-synthesised event fallback all correct. Design-table discrepancy (permission.updated vs permission.asked) correctly resolved in favour of SDK/INTERESTING_EVENTS."
}
```
