# I-00057 S04 Code Review Report

## What was reviewed

S03 (Tests) implementation: `tests/dashboard/test_chat_panel_default_collapsed.py`

## Files reviewed

| File | Change |
|------|--------|
| `tests/dashboard/test_chat_panel_default_collapsed.py` | New file (3 tests) |

## Pre-flight checks

- **Lint**: `make lint` — PASS (no violations on new file)
- **Format**: `make format` — PASS (`ruff format --check` clean on new file)

## Falsifiability analysis

### Test 1: `test_i00057_chat_panel_ships_collapsed`
Verifies: `'data-collapsed="true"' in html` AND `'data-collapsed="false"' not in html`

Pre-S01 template (git show main) had `data-collapsed="false"` on `#chat-panel` (line 38). The test would **FAIL** on pre-S01 code — PASS on post-S01. Correct.

### Test 2: `test_i00057_no_floating_left_minus_48_toggle`
Verifies: `'style="left: -48px;"' not in html` AND `'id="chat-toggle-tab"' not in html`

Pre-S01 template had `<button id="chat-toggle-tab" ... style="left: -48px;">` (lines 11 and 16). The test would **FAIL** on pre-S01 code — PASS on post-S01. Correct.

### Test 3: `test_i00057_collapse_and_expand_affordances_present`
Verifies: `'aria-label="Collapse chat panel'` AND `'aria-label="Expand chat panel'` — both present

Pre-S01 template only had `aria-label="Collapse chat panel (Cmd+\)"` on the floating tab (line 17). There was **no expand affordance** in static HTML. The test would **FAIL** on pre-S01 code — PASS on post-S01. Correct.

## Test quality review

### Specific values (not just shape) ✓
Each test verifies exact substrings, not just tag presence:
- `data-collapsed="true"` AND `data-collapsed="false" not in` — both halves
- `style="left: -48px;"` AND `id="chat-toggle-tab"` — both halves
- `aria-label="Collapse chat panel"` AND `aria-label="Expand chat panel"` — both halves

### Real-DB integration discipline ✓
Uses `db_session` from `tests/integration/conftest.py` (testcontainer-backed). `create_app()` + `dependency_overrides[get_db]` pattern follows the project standard (same as `test_jobs_filter_ui.py`). No DB mocks.

### Test isolation ✓
Each test calls `client.get(f"/project/{test_project.id}/code")` fresh. Uses function-scoped `test_project` fixture. No localStorage dependency — correct for server-rendered HTML tests.

### Convention conformance ✓
- File location: `tests/dashboard/test_chat_panel_default_collapsed.py` — follows existing dashboard test layout
- Naming: `test_*.py`, `def test_*` — correct
- Imports: follows project style (`from __future__ import annotations`, `TYPE_CHECKING`)

## Test run

```
tests/dashboard/test_chat_panel_default_collapsed.py::test_i00057_chat_panel_ships_collapsed PASSED
tests/dashboard/test_chat_panel_default_collapsed.py::test_i00057_no_floating_left_minus_48_toggle PASSED
tests/dashboard/test_chat_panel_default_collapsed.py::test_i00057_collapse_and_expand_affordances_present PASSED
```

3 passed, 0 failed.

Coverage threshold warning (18% vs 46%) is a pre-existing global config issue, not introduced by this file.

## Notes

- The `test_project` fixture is re-exported from `tests/integration/conftest.py` via `tests/dashboard/conftest.py` — standard pattern in this codebase.
- The `client` fixture temporarily pops `IW_CORE_EXPECTED_INSTANCE_ID` to avoid live-DB guard triggering during test app creation — same pattern as `test_jobs_filter_ui.py`.

## Verdict

**PASS** — all review criteria met, no mandatory fixes.
