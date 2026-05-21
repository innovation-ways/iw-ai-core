# CR-00068 S01 — Frontend Implementation Report

**Work Item**: CR-00068 — AI Assistant — Remove Per-Tab Model Bar
**Step**: S01
**Agent**: frontend-impl
**Completion Status**: complete

## What Was Done

Removed the redundant per-tab model bar (`#chat-assistant-tab-model-bar`) from the AI Assistant panel — the model picker remains accessible via the settings panel. The small model badge on each tab-strip button is unchanged.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/chat_assistant/panel.html` | Removed the model-bar `<div>` block and its `id="chat-assistant-tab-model-bar"` / `id="chat-assistant-tab-model-badge"` / `id="chat-assistant-tab-model-dropdown"` / `id="chat-assistant-tab-model-label"` elements; removed the bar's line from the collapsed-state hide CSS rule |
| `dashboard/static/chat_assistant/chat.js` | Deleted `_updateTabModelBar()`, `_hideTabModelBar()`, `_populateTabModelDropdown()`, `_selectTabModel()` functions; removed `_availableModels` state variable; removed all call sites and the per-tab model badge click listener and document outside-click branch; retained `_defaultModel`, `_refreshModels()`, `_scheduleModelRefresh()`, `_modelShortName()`, and the tab-strip `.chat-assistant-tab-model-badge` class; removed dangling `_populateTabModelDropdown()` call from `_refreshModels()` |
| `tests/dashboard/test_cr00068_model_bar_removed.py` | New regression test: 10 assertions across 4 test classes covering element absence, CSS selector validity, JS function/variable absence, and tab-strip badge retention |

## Quality Gates

- **`make lint`**: Node `--check` on `chat.js` passed; `scripts/check_templates.py` passed; ruff E501 errors on `test_phase2_apply_no_self_deadlock.py` are pre-existing and unrelated to this work item
- **`make format-check`**: not run separately (covered by lint gate)
- **`uv run pytest tests/dashboard/test_cr00068_model_bar_removed.py`**: 10 passed in 0.19s

## Post-Edit Grep Confirmation

All seven removed identifiers return zero matches in `chat.js`:
- `chat-assistant-tab-model-bar` — 0
- `chat-assistant-tab-model-dropdown` — 0
- `chat-assistant-tab-model-label` — 0
- `_updateTabModelBar` — 0
- `_hideTabModelBar` — 0
- `_populateTabModelDropdown` — 0
- `_selectTabModel` — 0
- `_availableModels` — 0

`chat-assistant-tab-model-badge` still appears in `chat.js` as a CSS class on tab-strip buttons (correct — the tab-strip badge is kept).

## Blockers

None.

## Notes

- The `test_tab_strip_model_badge_class_in_panel_html` assertion was replaced with `test_tab_strip_model_badge_class_still_present_in_js` and `test_tab_strip_model_badge_includes_are_intact` — the former was impossible to satisfy because the tab-strip badge class is injected by JavaScript at render time, not present in the static template.
- No CSS in `chat.css` was targeted or modified — the bar used only inline Tailwind classes.
- No existing tests were found asserting on the model bar's presence; no test updates were required.