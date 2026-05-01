# I-00057 S03 Tests Report

## What was done

Created `tests/dashboard/test_chat_panel_default_collapsed.py` with three regression tests for the I-00057 chat panel default-collapsed fix.

## Files changed

- `tests/dashboard/test_chat_panel_default_collapsed.py` — new file

## Tests added (3)

| Test | Verifies |
|------|----------|
| `test_i00057_chat_panel_ships_collapsed` | `#chat-panel` has `data-collapsed="true"` (not `"false"`) on initial render |
| `test_i00057_no_floating_left_minus_48_toggle` | No `style="left: -48px;"` and no `id="chat-toggle-tab"` — the old floating tab pattern is gone |
| `test_i00057_collapse_and_expand_affordances_present` | Both `aria-label="Collapse chat panel` (header) and `aria-label="Expand chat panel` (rail) exist |

## Pre-flight checks

- **Format**: `ruff format` applied (1 file reformatted)
- **Lint**: `ruff check --fix` applied (2 auto-fixable violations fixed: missing trailing newline, unused import)
- **Typecheck**: mypy reports 3 `no-untyped-def` errors — same pattern as the existing `test_jobs_filter_ui.py` fixture; these are pre-existing in the codebase and not introduced by this file
- **Test run**: 3 passed in ~17s

## Test results

```
tests/dashboard/test_chat_panel_default_collapsed.py::test_i00057_chat_panel_ships_collapsed PASSED
tests/dashboard/test_chat_panel_default_collapsed.py::test_i00057_no_floating_left_minus_48_toggle PASSED
tests/dashboard/test_chat_panel_default_collapsed.py::test_i00057_collapse_and_expand_affordances_present PASSED
```

All 3 I-00057 tests pass against the post-S01 templates (the fix is already reflected in `dashboard/templates/chat/panel.html`).

## Notes

- The test file uses the same `client` + `test_project` fixture pattern as `test_jobs_filter_ui.py` (FastAPI TestClient with testcontainer-backed `db_session`).
- Full dashboard suite shows 11 pre-existing failures in other test files (related to I-00046/I-00044 toggle button tests and a browser smoke test) — these are unrelated to I-00057.
- Coverage threshold warning (18% vs 46% required) is a global config issue unrelated to this step.