# I-00046 S03 Tests Report

## What Was Done

Created `tests/dashboard/test_chat_panel_layout_i00046.py` — a fast Jinja-only template test file that structurally verifies both I-00046 bugs are fixed.

**Test classes:**

- `TestChatPanelToggleButton` (4 tests) — bug (a): duplicate ID, overflow-hidden removal, min-h-0 addition, toggle button presence
- `TestCodeContentRootContainment` (1 test) — bug (c): `#code-content-root` min-h-0 containment

All 5 tests **PASS** against the post-fix templates (S01 already applied the fix).

## RED Phase Analysis

Per the design doc's root cause analysis, the pre-fix templates had:
- A duplicate `id="chat-panel-slot"` on an inner `<div>` in `panel.html` (line 9)
- `lg:overflow-hidden` on the outer `<aside>` in `project_code.html` (line 123)
- No `lg:min-h-0` on `#code-content-root` (line 108)

The tests are written to detect exactly these conditions. Since S01 already applied the fix, tests pass. The test assertions target the **specific element** (via regex match on the opening tag) rather than the whole page HTML, ensuring semantic correctness.

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | Fixed (trailing newline) |
| `make lint` | Ok |
| `make typecheck` | Ok |

## Test Results

```
tests/dashboard/test_chat_panel_layout_i00046.py
  TestChatPanelToggleButton::test_no_duplicate_chat_panel_slot_id     PASSED
  TestChatPanelToggleButton::test_aside_does_not_have_overflow_hidden  PASSED
  TestChatPanelToggleButton::test_aside_has_min_h_0                    PASSED
  TestChatPanelToggleButton::test_toggle_tab_button_is_present         PASSED
  TestCodeContentRootContainment::test_code_content_root_has_min_h_0   PASSED

5 passed in 0.04s
```

Full `make test-unit`: **1910 passed, 2 skipped**

## Files Changed

- `tests/dashboard/test_chat_panel_layout_i00046.py` — new

## Notes

- The `jinja_env` fixture was copied into the new test file (not shared via conftest.py) — `tests/dashboard/conftest.py` only re-exports DB integration fixtures, it has no Jinja environment fixture.
- Pre-fix failures would be: duplicate ID count=2, aside_tag contains overflow-hidden, root_tag missing min-h-0. The tests detect each symptom precisely at the element level.