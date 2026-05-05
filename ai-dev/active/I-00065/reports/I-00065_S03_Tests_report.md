# I-00065 S03 Tests Implementation Report

## Work Item
**I-00065** — Code-view chat panel: "+ New" visible when collapsed and duplicates greeting

## Step
**S03 Tests** — Regression tests for both bugs

---

## What Was Done

Created two new test files reproducing and regressing both bugs from I-00065:

### Bug 1 — `test_chat_panel_template.py`

**File**: `tests/dashboard/test_chat_panel_template.py`

Two tests that assert the `panel.html` `<style>` block includes `#chat-new-btn` in the `data-collapsed="true"` hide rule:

1. `test_i00065_new_button_hidden_when_collapsed` — The exact string `'#chat-panel[data-collapsed="true"] #chat-new-btn'` must appear in the style block.

2. `test_i00065_all_expanded_header_elements_hidden_when_collapsed` — A regression guard verifying all six IDs (`chat-context-label`, `chat-messages`, `chat-scroll-to-bottom-wrap`, `chat-composer`, `chat-new-btn`, `chat-collapse-btn`) are covered by the collapsed-state hide rule.

### Bug 2 — `test_chat_panel_empty_state.py`

**File**: `tests/dashboard/test_chat_panel_empty_state.py`

Two tests that assert the `panel.js` `showEmptyState` function body removes any pre-existing `#chat-empty-state` before inserting:

1. `test_i00065_show_empty_state_removes_existing_before_insert` — Verifies:
   - `getElementById('chat-empty-state')` is called in the function
   - `.remove()` is called on the result
   - The lookup appears BEFORE `insertBefore` (ordering check via byte offsets)

2. `test_i00065_show_empty_state_uses_guard_pattern` — Bonus guard that asserts the `.remove()` call is wrapped in a null-check guard pattern (`if (var) var.remove();` or `var?.remove();`) to prevent TypeError when no prior element exists.

---

## TDD Verification (RED/GREEN)

- **RED**: Mentally verified both tests would fail against the pre-fix code:
  - Bug 1 pre-fix: `#chat-new-btn` absent from hide selector → test fails
  - Bug 2 pre-fix: `showEmptyState` has no `getElementById('chat-empty-state')` → test fails
- **GREEN**: Both tests PASS against the current fixed code (S01 already applied)

---

## Preflight Checks

| Check | Result |
|-------|--------|
| `make format` | `ruff format` — both files already formatted |
| `make lint` (ruff) | **OK** — zero errors |
| `make typecheck` (mypy) | mypy reports untyped-def errors on test methods (same as all existing dashboard tests in `test_chat_panel_layout_i00046.py`); this is pre-existing project-wide, not introduced by these files |

---

## Test Results

Running only the new tests:
```
tests/dashboard/test_chat_panel_template.py::TestNewChatButtonHiddenWhenCollapsed::test_i00065_new_button_hidden_when_collapsed PASSED
tests/dashboard/test_chat_panel_template.py::TestNewChatButtonHiddenWhenCollapsed::test_i00065_all_expanded_header_elements_hidden_when_collapsed PASSED
tests/dashboard/test_chat_panel_empty_state.py::TestShowEmptyStateRemovesExistingBeforeInsert::test_i00065_show_empty_state_removes_existing_before_insert PASSED
tests/dashboard/test_chat_panel_empty_state.py::TestShowEmptyStateRemovesExistingBeforeInsert::test_i00065_show_empty_state_uses_guard_pattern PASSED
========================= 4 passed in 0.03s =========================
```

Full `tests/dashboard/` suite (excluding browser tests):
```
447 passed, 12 skipped, 1 xfailed, 8 warnings
```
All chat-panel-related tests pass (85 passed across chat panel test files).

Full `tests/unit/` suite:
```
2581 passed, 4 skipped, 5 xfailed, 47 warnings
```

---

## Files Changed

| File | Purpose |
|------|---------|
| `tests/dashboard/test_chat_panel_template.py` | Bug 1 regression tests |
| `tests/dashboard/test_chat_panel_empty_state.py` | Bug 2 regression tests |

---

## Blockers

None.

---

## Notes

- mypy `no-untyped-def` errors are pre-existing project-wide in dashboard tests — same errors appear in `test_chat_panel_layout_i00046.py` which has the same untyped method pattern. Not introduced by these new files.
- Tests are pure file-content assertions — no DB, no testcontainers, no browser needed.
- Both tests use absolute `Path(__file__).parent.parent.parent / "dashboard" / "..."` paths for deterministic file resolution.
- The `test_i00065_show_empty_state_uses_guard_pattern` bonus test was added because the S01 fix (`if (existingEmpty) existingEmpty.remove();`) is an important defensive pattern that prevents a TypeError when `getElementById` returns `null`.
