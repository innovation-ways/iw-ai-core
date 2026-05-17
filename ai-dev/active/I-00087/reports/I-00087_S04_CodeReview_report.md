# I-00087 S04 Code Review Report — Tests (S03)

**Step**: S04 (CodeReview)
**Work Item**: I-00087
**Step Reviewed**: S03 (tests-impl)
**Reviewer**: code-review-impl
**Date**: 2026-05-17

---

## Summary

S03 added `tests/dashboard/test_chat_panel_event_protocol.py` with 8 tests that pin the
chat panel's wire-protocol contract against the opencode SDK. All gates pass. The tests are
well-structured and all 7 required test names from the design are present plus a well-executed
RED evidence test. Two minor weaknesses are noted (MEDIUM_FIXABLE + LOW); neither blocks merge.

**Verdict: PASS**

---

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | PASS — all checks passed |
| `make format-check` | PASS — 743 files already formatted |

---

## Test Execution

```
uv run pytest tests/dashboard/test_chat_panel_event_protocol.py -v --no-cov
8 passed in 0.04s
```

```
uv run pytest tests/dashboard/test_chat_router.py tests/unit/test_chat_client.py -v --no-cov
52 passed in 13.69s  — no regressions
```

---

## Checklist Results

### 1. Coverage of TDD Approach (7/7 required + 1 bonus)

All seven test names from the design's TDD Approach table are present:

| Required test | Present |
|---|---|
| `test_chat_js_registers_every_interesting_event` | ✓ |
| `test_chat_js_reads_properties_delta_for_streaming_text` | ✓ |
| `test_chat_js_history_reads_info_and_parts` | ✓ |
| `test_chat_js_preserves_session_storage_key` | ✓ |
| `test_chat_js_passes_last_event_id_on_reconnect` | ✓ |
| `test_chat_js_listens_for_session_idle` | ✓ |
| `test_chat_js_distinguishes_properties_from_data` | ✓ |
| `test_starter_listener_set_would_have_failed_protocol_check` | ✓ (bonus RED) |

### 2. Assertion Strength

Most assertions are strong and mutation-resilient:

- `assert not missing` where `missing = set(INTERESTING_EVENTS) - registered` — strong ✓
- `assert "'iw-chat-session-' + _tabId" in js` — exact string match ✓
- `assert "last_event_id=" in js` — matches executable code (chat.js:174) ✓
- `assert "data.properties" in js` — matches executable code (chat.js:259: `var props = (data && data.properties) || null`) ✓
- `assert "data.message" in js` — matches executable code (chat.js:271) ✓
- `assert "session.idle" in registered` — specific set-membership check ✓
- `assert ".info" in body` — uses `.info` (not just `"info"`), reasonable for JS source ✓
- `assert ".parts" in body` — specific, matches `entry.parts` in `_loadHistory` ✓

One weakness found (see Findings #1 below): `"properties.delta"` and `"properties.part"`
in `test_chat_js_reads_properties_delta_for_streaming_text` match comments only.

### 3. RED Evidence

- **Test ID**: `test_starter_listener_set_would_have_failed_protocol_check` ✓
- **Missing set documented**: `{'message.part.updated', 'permission.replied', 'session.error', 'session.updated', 'tool.execute.after', 'tool.execute.before'}` — non-empty, plausible ✓
- **Mechanism**: in-test `PRE_FIX_NAMED_EVENTS` fixture — no runtime mutation of `chat.js` ✓
- **Post-fix confirmation**: `test_chat_js_registers_every_interesting_event` passes on live `chat.js` ✓

No `git stash`, `git checkout`, `git show ... > path`, or file-copy anti-patterns detected.

### 4. Test Isolation

- No DB fixtures (`db_session`, `pg_engine`, testcontainer) used — pure file-read + regex ✓
- Deterministic: reads `chat.js` from a fixed path relative to the test file ✓
- No randomness, no network calls, no time-dependent logic ✓

### 5. Scope Discipline

`files_changed` contains only `tests/dashboard/test_chat_panel_event_protocol.py`.
No modifications to `chat.js`, `orch/chat/filters.py`, or any other production file ✓

---

## Findings

### Finding 1 — MEDIUM_FIXABLE

**Category**: testing
**File**: `tests/dashboard/test_chat_panel_event_protocol.py`
**Lines**: 79–83 (`test_chat_js_reads_properties_delta_for_streaming_text`)

**Description**: Both `assert "properties.delta" in js` and `assert "properties.part" in js`
pass due to **comments** in `chat.js` (lines 282, 295-296), not executable code.
The actual handler uses `props.delta` and `props.part.text` where
`props = data && data.properties` (chat.js:259, 288, 303-304). This means:
- The assertion would **pass** if someone added a comment mentioning `properties.delta`
  but changed the actual handler to use the wrong accessor.
- The assertion would **fail** if comments were removed while the code remained correct
  (false negative).

**Suggestion**: Change assertions to match actual executable code:
```python
assert "props.delta" in js, (
    "_handleEvent must read props.delta (= data.properties.delta) for streaming chunks"
)
assert "props.part.text" in js or "props.part &&" in js, (
    "_handleEvent must access props.part.text for finalised TextPart content"
)
```
Both strings appear in real code paths (chat.js:288, 303-304) and correctly fail
if the handler reverts to the old `data.text || data.content || data.delta` shape.

---

### Finding 2 — LOW

**Category**: testing
**File**: `tests/dashboard/test_chat_panel_event_protocol.py`
**Lines**: 93 (`test_chat_js_history_reads_info_and_parts`)

**Description**: The regex `r"function\s+_loadHistory\b[\s\S]*?\n\s*\}\s*\n"` uses
a non-greedy `[\s\S]*?` that stops at the **first** standalone `}` line. If `_loadHistory`
ever gains an early guard block (`if (!sid) { return; }`) whose closing `}` lands on
its own line, the captured body would be truncated before the `entry.info` / `entry.parts`
accesses, causing a false failure. Currently functional: `_loadHistory` starts with
a `fetch(…).then(…)` chain whose inner `}` lines are never standalone.

**Suggestion**: Use a non-`}` anchor or check the full file for the key patterns within
proximity of `_loadHistory`. Alternatively, `re.search(r"_loadHistory", body)` combined
with `re.search(r"entry\.info", body)` (two separate assertions) avoids the truncation risk.

---

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00087",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "testing",
      "file": "tests/dashboard/test_chat_panel_event_protocol.py",
      "line": 79,
      "description": "assert 'properties.delta' in js and assert 'properties.part' in js pass due to comments (chat.js:282,295-296), not executable code. Handler uses props.delta / props.part.text where props = data.properties. Assertion is resilient to full regressions but could pass if comments exist while code is wrong.",
      "suggestion": "Replace with 'props.delta' in js and 'props.part.text' in js (or 'props && props.part') to anchor assertions to actual executable code paths."
    },
    {
      "severity": "LOW",
      "category": "testing",
      "file": "tests/dashboard/test_chat_panel_event_protocol.py",
      "line": 93,
      "description": "_loadHistory regex stops at first standalone } line; could prematurely truncate function body if function gains early guard blocks.",
      "suggestion": "Use two independent assertions (re.search for _loadHistory presence, then entry.info / entry.parts in full file scope) rather than a fragile brace-counting regex."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "8 passed in 0.04s (new); 52 passed in 13.69s (existing chat tests — no regressions)",
  "notes": "RED evidence is correct and uses the approved in-test fixture approach. No banned anti-patterns (no git revert, no source mutation). Scope is clean (test-only). The MEDIUM_FIXABLE finding is a quality improvement, not a correctness blocker."
}
```
