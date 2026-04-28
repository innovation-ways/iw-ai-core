# I-00044_S03_Tests_prompt

**Work Item**: I-00044 — Code View Chat Panel — Ugly Collapse State and Viewport Drift
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00044/I-00044_Issue_Design.md` — design document (root cause, AC, test sketch)
- `ai-dev/active/I-00044/reports/I-00044_S01_Frontend_report.md` — S01 implementation details
- `tests/dashboard/test_code_layout_fixes.py` — established template-rendering test pattern to follow
- `tests/dashboard/conftest.py` — shared dashboard test fixtures
- `dashboard/templates/project_code.html` — modified template (Bug 2 fix)
- `dashboard/templates/chat/panel.html` — modified template (Bug 1 fix)

## Output Files

- `tests/dashboard/test_i00044_chat_panel_layout.py` — new test file (create)
- `ai-dev/active/I-00044/reports/I-00044_S03_Tests_report.md` — step report

---

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I-00002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "grid-rows" in html` (only checks substring exists anywhere)
- GOOD: `assert "lg:grid-rows-[1fr]" in page_body_match.group(0)` (checks EXACT class on SPECIFIC element)
- BAD: `assert "Chat" in html` (matches anywhere — even in "Chat — Architecture" header)
- GOOD: verify the "Chat" text is inside the collapse toggle element, not just anywhere in the page

---

## Context

You are writing reproduction and regression tests for I-00044, which fixed two frontend bugs:

- **Bug 1**: The chat panel's collapsed state showed only a bare `<` chevron (no label/icon).
  **Fix**: A slide-out toggle tab with a chat icon, rotated "Chat" label, and expand icon.
- **Bug 2**: The `#page-body` CSS grid lacked `grid-template-rows`, causing the row to
  auto-size to content height and overflow into `<main>` (which scrolls), dragging the chat
  panel out of view when long modules are selected.
  **Fix**: `lg:grid-rows-[1fr]` added to `#page-body`.

These are **template structure tests** — no browser, no DB, fast. Follow exactly the same
Jinja2-rendering pattern as `tests/dashboard/test_code_layout_fixes.py`.

---

## Requirements

### 1. Create `tests/dashboard/test_i00044_chat_panel_layout.py`

The file must open with a docstring explaining:
- Which incident it covers (I-00044)
- That all tests FAIL against pre-fix code and PASS after S01
- The Jinja-rendering approach (no browser, no DB)

**Follow `test_code_layout_fixes.py` exactly** for:
- The `_template_dir()` helper
- The `jinja_env` fixture (with all stubbed filters: `intcomma`, `timeago`, `fmt_ts_time`,
  `localdt`; and globals: `url_for`, `is_db_stale`)
- The `mock_request` pattern for templates that use `request.url.path`

### 2. Test: `TestBug2GridRowConstraint`

Class with at least two test methods:

**`test_page_body_has_grid_rows_1fr`**

Render `project_code.html` with dummy context. Extract the `#page-body` opening tag using
`re.search(r'<div[^>]+id="page-body"[^>]*>', html)`. Assert:
- The element exists
- `"lg:grid-rows-[1fr]"` is present inside the tag's class attribute

This test FAILS against pre-S01 code (the class was not there) and PASSES after.

**`test_page_body_grid_height_preserved`**

Same render. Assert the `#page-body` opening tag still contains:
- `"lg:h-[calc(100vh-12rem)]"` — the height constraint that existed before the fix must
  not have been accidentally removed
- `"lg:grid-cols-[1fr_var(--chat-width)]"` — the column layout must still be present

This is a regression guard: someone refactoring the grid must not silently drop either
existing class.

### 3. Test: `TestBug1CollapseToggleAffordance`

Class with at least three test methods:

**`test_toggle_tab_has_chat_label`**

Render `chat/panel.html` (no context variables needed — it's a static fragment). Assert:
- A "Chat" label string exists in the rendered HTML
- The label must appear inside or adjacent to the toggle tab element — NOT just in the
  panel header's context label (`#chat-context-label`).
  Strategy: locate the toggle tab element by its `id="chat-toggle-tab"` and assert "Chat"
  is in the substring after that point (within a reasonable range before the next major
  element). Use `re.search(r'id="chat-toggle-tab"[^>]*>(.{0,500})', html, re.DOTALL)` and
  check the captured group contains "Chat".

**`test_toggle_tab_has_aria_label_with_chat`**

Render `chat/panel.html`. Find the element with `id="chat-toggle-tab"`. Assert:
- `aria-label` attribute is present on that element
- The `aria-label` value contains "chat" (case-insensitive) or "Chat"
- The `aria-label` is NOT empty

**`test_collapsed_state_is_not_bare_chevron_only`**

Render `chat/panel.html`. Assert that the collapsed state CSS/markup does NOT rely SOLELY
on the bare old `#chat-collapse-btn` approach:
- The element `id="chat-toggle-tab"` must be present (the new toggle tab)
- The element must contain either a `<svg` (icon) or the text "Chat" within its subtree

This test is the primary SEMANTIC guard: it would fail against the pre-fix code because
`#chat-toggle-tab` did not exist.

### 4. Test: `TestBug1KeyboardAccessibility`

**`test_toggle_tab_is_a_button`**

Render `chat/panel.html`. Find `id="chat-toggle-tab"`. Assert:
- The opening tag is `<button` (not `<div`, not `<span`)

**`test_mobile_elements_unchanged`**

Render `chat/panel.html`. Assert that pre-existing mobile elements are still present:
- `id="chat-close-btn"` exists
- `id="chat-drawer-open"` exists (in the drawer button outside `#chat-panel`)
- `id="chat-drawer-backdrop"` exists

This prevents regressions where Bug 1 fix accidentally removes mobile UI.

### 5. Run all tests before reporting

```bash
make test-unit
```

All tests in `test_i00044_chat_panel_layout.py` must PASS.
All previously passing tests must continue to PASS.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — run and fix any issues
2. `make typecheck` — zero errors on the new test file
3. `make lint` — zero errors
4. `make test-unit` — all tests pass

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00044",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_i00044_chat_panel_layout.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
