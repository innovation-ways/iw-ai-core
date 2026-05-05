# CR-00034 S01 Tests Report

## What Was Done

Implemented the two assertion rewrites + one import addition specified in the CR-00034 design document:

1. **Added `import html`** to the stdlib import group (alphabetically between `from __future__ import annotations` and `from typing import TYPE_CHECKING`).
2. **Renamed local `html` → `body`** in `test_long_message_truncated_and_full_text_in_dom` (lines 88–98) to avoid shadowing the stdlib `html` module, then used `html.escape(long_msg, quote=True)` in the assertion.
3. **Renamed local `html` → `body`** in `test_101_char_message_is_truncated` (lines 236–244) using the same pattern, then used `html.escape(msg, quote=True)` in the assertion.

## Shadowing Fix Approach

Chose the **preferred approach: rename the local response variable** from `html` to `body` in both affected test functions. This cleanly resolves the shadowing collision without requiring pre-computation of escaped values before the response assignment.

## Files Changed

- `tests/dashboard/test_i00067_recent_activity_truncation.py`

## Test Results

```
tests/dashboard/test_i00067_recent_activity_truncation.py::test_long_message_truncated_and_full_text_in_dom PASSED
tests/dashboard/test_i00067_recent_activity_truncation.py::test_short_message_not_truncated_no_affordance PASSED
tests/dashboard/test_i00067_recent_activity_truncation.py::test_exactly_100_char_message_not_truncated PASSED
tests/dashboard/test_i00067_recent_activity_truncation.py::test_batch_entity_link_routing_unchanged PASSED
tests/dashboard/test_i00067_recent_activity_truncation.py::test_activity_text_modal_included_in_page PASSED
tests/dashboard/test_i00067_recent_activity_truncation.py::test_null_message_falls_back_to_event_type PASSED
tests/dashboard/test_i00067_recent_activity_truncation.py::test_101_char_message_is_truncated PASSED

7 passed, 0 failed
```

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok (ruff auto-fixed, 1 file reformatted) |
| `make typecheck` | ok (mypy: no issues in 224 source files) |
| `make lint` | ok (ruff check: all passed) |

## Observations

- The TDD "RED" phase (pre-flight run) confirmed 7/7 tests passed before editing.
- The edited file still passes 7/7 after the change — as expected, since `"E"*200` and `"X"*101` contain no characters that `html.escape` with `quote=True` would modify.
- `make format` reported the file needed reformatting (the multi-line assertion at line 96 exceeded the line-length limit); `ruff format` auto-fixed it.
- No other assertions in the file were touched, consistent with the CR scope.
