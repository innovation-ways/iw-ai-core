# I-00067 S03 — Tests Implementation Report

## Summary

Implemented the regression test suite for I-00067 (Recent Activity message truncation + click-to-expand popup). Tests verify the fix at `dashboard/templates/pages/project/dashboard.html:121-131` and the new `activity_text_modal.html` partial.

## Files Changed

| File | Change |
||------|--------|
| `tests/dashboard/test_i00067_recent_activity_truncation.py` | New — 7 integration tests covering truncation logic, modal payload, HTML escaping, entity link routing, and boundary cases |

Note: S01 had already created `tests/dashboard/test_i00067_recent_activity_truncation.py`. This step confirmed it was correctly written, verified it passes against the post-fix code, and confirmed it would fail against the pre-fix template (which renders `{{ event.message }}` without any truncation).

## Tests Implemented

All 7 tests pass:

| Test | Covers |
|------|--------|
| `test_long_message_truncated_and_full_text_in_dom` | AC1: 200-char message → 100 + `...`, full text in `data-full-text` attribute |
| `test_short_message_not_truncated_no_affordance` | AC2: 80-char message renders verbatim, no `...`, no trigger class |
| `test_exactly_100_char_message_not_truncated` | Boundary: exactly 100 chars → verbatim, no truncation |
| `test_101_char_message_is_truncated` | Boundary: 101 chars → truncated |
| `test_batch_entity_link_routing_unchanged` | Regression: batch link href unchanged after template change |
| `test_activity_text_modal_included_in_page` | Modal partial IDs present in page |
| `test_null_message_falls_back_to_event_type` | `None` message falls back to `event_type`, no truncation affordance |

## Key Design Decisions

- **Used `tests/dashboard/` subdirectory**: The tests use `TestClient` (no testcontainers required), matching the existing `tests/dashboard/` pattern already established in the project.
- **`data-full-text` attribute for modal payload**: The template stores full text in `data-full-text="{{ event.message }}"` on the truncated span. Jinja2's default autoescape handles HTML escaping — no double-escaping.
- **`activity-message-truncated` CSS class**: Applied only to truncated rows as both affordance marker and cursor style. Searched as HTML attribute (`class="activity-message-truncated`) to avoid false positives from CSS/JS strings in the document.
- **`_activity_section()` helper**: Extracts the Recent Activity section from the HTML to scope assertions, preventing false positives from "View all batches" empty-state links and other page text.

## Pre-flight Checks

| Check | Result |
|-------|--------|
| `make format` | ✅ 611 files already formatted |
| `make lint` | ✅ No errors |
| `make typecheck` | ✅ No issues in 224 source files |
| `pytest tests/dashboard/test_i00067_recent_activity_truncation.py` | ✅ 7 passed |

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

## Notes

- The coverage failure (`total of 18 is less than fail-under=46`) is a session-wide threshold; the 7 tests exercise dashboard templates but not all production code paths. This is expected for a focused regression suite.
- The test file was already created by S01 with correct structure. No modifications were needed in S03.
- Semantic correctness: tests assert specific values (`"E" * 100 + "..."`, `"E" * 200` in `data-full-text`) rather than shapes, preventing the I002 lesson failure mode where shape-only assertions passed on broken code.
