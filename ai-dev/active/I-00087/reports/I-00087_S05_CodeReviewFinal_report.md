# I-00087 S05 — Final Cross-Agent Review Report

**Work item**: I-00087 — AI Assistant chat panel does not render model responses
**Step**: S05 (CodeReview_Final)
**Steps reviewed**: S01, S02, S03, S04
**Date**: 2026-05-17

---

## Summary

The implementation (S01) correctly aligns `chat.js` with the opencode 1.15 wire protocol across all three defect areas (listener names, payload extraction, history reload). The tests (S03) provide solid coverage and the RED evidence approach is sound. Both per-step reviews (S02, S04) passed their own gates cleanly.

**Two unresolved findings** carry over from the per-step reviews:

1. **HIGH** — `_loadHistory` never resets `_currentAssistantEl` after its `forEach` loop. S02 identified this and rated it MEDIUM_FIXABLE, but the fix was never applied. At the final review level, with AC1 explicitly listed as a mandatory criterion, this is escalated to HIGH.
2. **MEDIUM_FIXABLE** — One test assertion in `test_chat_panel_event_protocol.py` matches a comment, not executable code. S04 identified this and it remains unfixed.

**Verdict: fail** — one HIGH finding must be resolved before merge.

---

## Pre-Review Quality Gates

| Gate | Result |
|---|---|
| `make lint` | PASS — all checks passed (ruff + node --check + check_templates.py) |
| `make format-check` | PASS — 743 files already formatted |

No new violations in any file touched by S01–S04.

---

## Test Results

```
uv run pytest tests/dashboard/test_chat_router.py tests/unit/test_chat_client.py tests/dashboard/test_chat_panel_event_protocol.py -v --no-cov

60 passed in 13.63s
```

S03 added 8 tests (the design pinned 7; S03 added a bonus RED-evidence test), so the total is 52 + 8 = 60.

---

## AC Traceability Matrix

| AC | Demonstrated by | Status |
|---|---|---|
| AC1 — Streaming replies render in real time | `_handleEvent` for `message.part.delta/updated`; `_appendOrUpdateAssistantMessage`; `test_chat_js_reads_properties_delta_for_streaming_text` | **PARTIAL** — fails for sessions with prior history (unresolved S02 finding; see F-001) |
| AC2 — History reloads across refresh/session switch | `_loadHistory` rewrite + sessionStorage; `test_chat_js_history_reads_info_and_parts`, `test_chat_js_preserves_session_storage_key` | PASS |
| AC3 — Tool calls produce a breadcrumb | `tool.execute.before/after` handlers in `_handleEvent`; `_appendToolCall`; `test_chat_js_registers_every_interesting_event` covers event registration | PASS |
| AC4 — Permission modal still works | `permission.asked` handler; `_showApprovalModal`; `test_chat_js_registers_every_interesting_event` covers registration | PASS |
| AC5 — Regression tests exist | `tests/dashboard/test_chat_panel_event_protocol.py` (8 tests); `test_starter_listener_set_would_have_failed_protocol_check` as RED evidence | PASS (with one weak assertion — F-002) |
| AC6 — Browser verification passes | S11 (qv-browser) — separate step, prompt exists at `prompts/I-00087_S11_BrowserVerification_prompt.md` | Pending S11 |

---

## Cross-File Consistency

**INTERESTING_EVENTS vs namedEvents:**

`orch/chat/filters.py:INTERESTING_EVENTS` = `{'message.part.updated', 'tool.execute.before', 'tool.execute.after', 'permission.asked', 'permission.replied', 'session.idle', 'session.updated', 'session.error'}` (8 events).

`chat.js` `namedEvents` (lines 189–210) includes all 8 plus 9 additional events. The JS set is a proper superset. `test_chat_js_registers_every_interesting_event` correctly checks `set(INTERESTING_EVENTS) - registered` and would catch any divergence. This test is mutation-resilient for the INTERESTING_EVENTS side.

**Payload accessors:**

`_handleEvent` uses `var props = (data && data.properties) || null` (line 259). All opencode-native event handlers read `props.*` correctly. Relay-synthesised events (`gap`, `reconnecting`, `error`, `relay.error`) read `data.*` directly. The asymmetry is documented with a comment block (lines 229–237). ✓

---

## Session-Continuity Audit

All six invariants confirmed present:

| Invariant | Lines |
|---|---|
| `'iw-chat-session-' + _tabId` set/read | 107, 117, 135, 160 |
| `last_event_id=` appended to stream URL | 174 |
| `_loadHistory(` called after reconnect | 118, 139 |
| `sessionStorage.removeItem` on `newSession()` | 107 |
| `switchSession` present and exported | 111, 130 |
| `_renderChip` present and called | 83, 89, 660 |

---

## Dedup Logic Review

`_appendOrUpdateAssistantMessage` checks `_currentAssistantId !== null` (not a prefix-format check). Dedup at the event level is keyed on `e.lastEventId`. Neither check assumes `msg_*` or `evt_*` format — safe. ✓

History reload passes `info.id` as the dedup key; streaming handlers pass `props.messageID || eid`. When these differ (new message in a new prompt), a new bubble is created. When they match (reconnect into an in-flight message), text accumulates into the same bubble. This is correct — except that the stale `_currentAssistantEl` bug (F-001) makes the check trigger for the wrong bubble.

---

## Security

All user-controlled text that enters `innerHTML` goes through `_escHtml`:
- `_appendUserMessage`: `_escHtml(text)` ✓
- `_appendToolCall`: `_escHtml(toolName)` + `_escHtml(argsStr)` ✓
- `_appendToolResult`: `_escHtml(resultStr)` ✓
- `_showApprovalModal`: `_escHtml(toolName)`, `_escHtml(argsStr)`, `_escHtml(rationale)` ✓
- `_renderChip`: `_escHtml(_context.title || _context.id)` ✓
- Assistant streaming text uses `textContent` (not innerHTML) ✓

No XSS risk. ✓

---

## Functional Doc Alignment

`I-00087_Functional.md` states five "What Changed" bullets. All five are implemented:
1. Streaming reply in a bubble — ✓ (with F-001 caveat on returning sessions)
2. Tool breadcrumb — ✓
3. Permission modal fires at the right moment — ✓
4. History reloads on refresh — ✓
5. Errors render as error messages — ✓

No drift requiring a doc update.

---

## Findings

### F-001 — HIGH: `_loadHistory` stale `_currentAssistantEl` breaks AC1 for sessions with prior history

**Severity**: HIGH
**Category**: code_quality / cross_step (unresolved from S02 review)
**File**: `dashboard/static/chat_assistant/chat.js`
**Lines**: 639–654 (`_loadHistory` forEach block)

**Description**:

`_clearMessages()` (line 638) resets `_currentAssistantEl = null` and `_currentAssistantId = null`. The `forEach` then calls `_appendOrUpdateAssistantMessage(info.id, text, true)` for each assistant history entry. `_appendOrUpdateAssistantMessage` with `isFinal=true` always creates a new DOM element and sets:

```js
_currentAssistantEl = wrap;   // points to the last history bubble after forEach ends
_currentAssistantId = eid;
```

After `_loadHistory` resolves, `_currentAssistantEl` is non-null and `_currentAssistantId` is non-null. When the user sends a new prompt and the first `message.part.delta` or `message.part.updated` event arrives, the accumulation branch in `_appendOrUpdateAssistantMessage`:

```js
if (!isFinal && _currentAssistantEl && _currentAssistantId !== null) {
```

evaluates to `true`, and the new streaming text is silently appended to the stale history bubble instead of creating a new bubble. AC1 — "an assistant message bubble is created on first delta" — fails for any session that has prior history.

This was S02's only finding (MEDIUM_FIXABLE). Escalated to HIGH here because AC1 is a mandatory acceptance criterion, and the bug triggers reliably for any returning user (the majority case after first use).

**Suggestion**:

Add two lines immediately after the `forEach` loop inside `_loadHistory`:

```js
        data.messages.forEach(function (entry) {
          // ... existing code ...
        });
        // Reset so the next prompt's streaming text creates a new bubble.
        _currentAssistantEl = null;
        _currentAssistantId = null;
```

Fix is two lines. Already suggested verbatim by S02.

---

### F-002 — MEDIUM_FIXABLE: Test assertions match comments, not executable code

**Severity**: MEDIUM_FIXABLE
**Category**: testing / cross_step (unresolved from S04 review)
**File**: `tests/dashboard/test_chat_panel_event_protocol.py`
**Lines**: 78–83 (`test_chat_js_reads_properties_delta_for_streaming_text`)

**Description**:

```python
assert "properties.delta" in js
assert "properties.part" in js
```

Both strings appear in **comments** in `chat.js` (line 282: `// Streaming text delta: properties.delta is…`; line 295: `// Full part snapshot: properties.part is…`), not in executable code. The actual handler reads `props.delta` and `props.part.text` (where `props = data.properties`).

This means the assertions would pass even if a future change removed the correct accessor and replaced it with the old `data.text || data.content` shape, as long as the comments were kept. Conversely, removing the comments while leaving correct code would cause a false failure.

**Suggestion** (per S04):

```python
assert "props.delta" in js, (
    "_handleEvent must read props.delta (= data.properties.delta) for streaming chunks"
)
assert "props.part.text" in js or "props.part &&" in js, (
    "_handleEvent must access props.part.text for finalised TextPart content"
)
```

Both strings appear in real code paths (`chat.js:288`, `chat.js:303–304`) and would fail if the handler reverted to the old shape.

---

## Review Result

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00087",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "fail",
  "findings": [
    {
      "severity": "HIGH",
      "category": "code_quality",
      "file": "dashboard/static/chat_assistant/chat.js",
      "line": 654,
      "description": "_loadHistory does not reset _currentAssistantEl/_currentAssistantId after its forEach loop. _appendOrUpdateAssistantMessage(isFinal=true) sets _currentAssistantEl to the last history bubble. The next streaming delta appends to that stale history bubble instead of creating a new one. AC1 fails for any session with prior history. This is the unresolved S02 MEDIUM_FIXABLE finding, escalated to HIGH because AC1 is a mandatory criterion.",
      "suggestion": "Add _currentAssistantEl = null; _currentAssistantId = null; after the forEach loop in _loadHistory (inside the .then callback)."
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "testing",
      "file": "tests/dashboard/test_chat_panel_event_protocol.py",
      "line": 78,
      "description": "assert 'properties.delta' in js and assert 'properties.part' in js pass due to comments in chat.js (lines 282, 295-296), not executable code. Actual handler uses props.delta and props.part.text. The test could pass with a regression if comments remain. Unresolved S04 finding.",
      "suggestion": "Replace with assert 'props.delta' in js and assert 'props.part.text' in js (or 'props.part &&') to anchor assertions to executable code paths."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "60 passed, 0 failed (52 existing + 8 new)",
  "notes": "All six session-continuity invariants present. INTERESTING_EVENTS fully covered by namedEvents (superset). All user-controlled innerHTML strings escape through _escHtml. Dedup logic is format-agnostic. Security clean. Two issues from prior per-step reviews were not resolved before S05: F-001 (HIGH, AC1 violation) and F-002 (MEDIUM_FIXABLE, weak test assertion). Functional doc matches implementation."
}
```
