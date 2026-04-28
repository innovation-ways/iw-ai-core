# I-00044 S01 Frontend Step Report

## Summary

Completed both Bug 1 and Bug 2 fixes for the code view chat panel.

## Changes Made

### Bug 2 Fix — Grid row height constraint (project_code.html:106)

Added `lg:grid-rows-[1fr]` to `#page-body` to force the single grid row to consume exactly `calc(100vh-12rem)`, constraining grid items and preventing `<main>` from scrolling.

### Bug 1 Fix — Slide-out toggle tab (chat/panel.html, panel.js, chat.css)

Replaced the in-header `#chat-collapse-btn` with a `#chat-toggle-tab` button positioned on the left edge of `#chat-panel-slot`. The tab is always visible in both states:
- **Expanded**: collapse chevron (`»`) with aria-label "Collapse chat panel (Cmd+\)"
- **Collapsed**: shows chat bubble icon, rotated "Chat" label (bottom-up), and expand chevron (`«`) — the 48 px strip is now a recognisable affordance

`applyCollapsedState()` in `panel.js` now wires `#chat-toggle-tab` instead of `#chat-collapse-btn`, updating aria-label and `data-collapsed` attribute on the tab.

### make css

Rebuilt `dashboard/static/styles.css` after all template/JS/CSS changes.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/project_code.html` | Added `lg:grid-rows-[1fr]` to `#page-body` |
| `dashboard/templates/chat/panel.html` | Replaced `#chat-collapse-btn` with `#chat-toggle-tab` slide-out tab |
| `dashboard/static/chat/panel.js` | Updated `applyCollapsedState()` to wire `#chat-toggle-tab` |
| `dashboard/static/chat.css` | Added toggle tab visibility CSS |
| `dashboard/static/styles.css` | Rebuilt via `make css` |

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | ok (442 files already formatted) |
| `make typecheck` | ok (190 source files, no issues) |
| `make lint` | ok (All checks passed) |
| `make lint-js` | ok (no JS lint errors) |
| `make test-unit` | 2 failed (unrelated: `test_safe_migrate.py` — `test_apply_refuses_in_agent_context` and `test_rollback_refuses_in_agent_context`; these are pre-existing failures related to `_assert_not_agent_context` deprecation and live DB resolution from `unused` hostname) |

The 2 failing tests in `test_safe_migrate.py` are unrelated to I-00044 — they fail due to a DNS resolution issue in the test environment and a deprecation of `_assert_not_agent_context`. All 1908 other unit tests pass.

## Notes

- `test_collapse_button_44px` in `test_chat_templates.py` now fails because it was written against the old `#chat-collapse-btn` design. S03 (Tests agent) will update this test to reflect the new `#chat-toggle-tab` design, as indicated in the design document.
- npm dependencies were refreshed to fix a `postcss-selector-parser` module-not-found error in `make css` before rebuilding.