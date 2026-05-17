# I-00087 S03 Tests Report

## What Was Done

Created `tests/dashboard/test_chat_panel_event_protocol.py` containing 8 tests that pin the chat panel's wire-protocol contract to the opencode SDK. All tests exercise the post-S01 `chat.js` via pure text/regex inspection — no DB, no testcontainer, no FastAPI client required.

## Files Changed

- `tests/dashboard/test_chat_panel_event_protocol.py` — new test file (8 tests)

## Test Results

```
8 passed in 0.04s
```

All tests pass against the post-S01 `chat.js`.

| Test | Status |
|------|--------|
| `test_chat_js_registers_every_interesting_event` | PASSED |
| `test_chat_js_reads_properties_delta_for_streaming_text` | PASSED |
| `test_chat_js_history_reads_info_and_parts` | PASSED |
| `test_chat_js_preserves_session_storage_key` | PASSED |
| `test_chat_js_passes_last_event_id_on_reconnect` | PASSED |
| `test_chat_js_listens_for_session_idle` | PASSED |
| `test_chat_js_distinguishes_properties_from_data` | PASSED |
| `test_starter_listener_set_would_have_failed_protocol_check` | PASSED |

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok (743 files already formatted) |
| `make typecheck` | ok (no issues in 255 source files) |
| `make lint` | ok (all checks passed; removed `print` statement flagged by T201) |

## TDD RED Evidence

**Test ID**: `tests/dashboard/test_chat_panel_event_protocol.py::test_starter_listener_set_would_have_failed_protocol_check`

**Mechanism**: The `PRE_FIX_NAMED_EVENTS` frozenset in the test file captures the exact strings that lived in `chat.js`'s `namedEvents` array before the I-00087 fix:

```python
PRE_FIX_NAMED_EVENTS = frozenset({
    "message.part", "message.snapshot", "message.complete", "message.updated",
    "tool.call", "tool.result", "permission.asked", "session.idle",
    "error", "gap", "reconnecting",
})
```

Running the same protocol-check logic against this fixture:

```
set(INTERESTING_EVENTS) - PRE_FIX_NAMED_EVENTS
= {'message.part.updated', 'permission.replied', 'session.error', 'session.updated',
   'tool.execute.after', 'tool.execute.before'}
```

This non-empty set IS the RED evidence — the pre-fix listener set would have failed `test_chat_js_registers_every_interesting_event`. The test `test_starter_listener_set_would_have_failed_protocol_check` asserts this set is non-empty and PASSES, confirming RED without reverting shipped source.

**Post-S01 contract test**: `test_chat_js_registers_every_interesting_event` passes against the live `chat.js` because the post-S01 `namedEvents` array includes all 8 members of `INTERESTING_EVENTS`.

## Notes

- The `_registered_event_names()` helper handles both the `namedEvents.forEach` array form (current pattern) and direct `addEventListener` string-literal calls.
- `test_chat_js_history_reads_info_and_parts` uses a regex to extract the `_loadHistory` function body and checks for `.info` and `.parts` accessors. The non-greedy match captures enough of the function to include the `entry.info` / `entry.parts` lines.
- The `print()` call suggested in the design doc's RED evidence section was removed because `make lint` (ruff T201) rejects it. The `missing` set value is documented statically in this report instead.
