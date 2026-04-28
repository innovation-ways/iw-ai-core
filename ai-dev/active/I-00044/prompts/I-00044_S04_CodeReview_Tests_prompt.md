# I-00044_S04_CodeReview_Tests_prompt

**Work Item**: I-00044 — Code View Chat Panel — Ugly Collapse State and Viewport Drift
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00044/I-00044_Issue_Design.md` — design document (AC and test sketch)
- `ai-dev/active/I-00044/reports/I-00044_S03_Tests_report.md` — S03 implementation report
- `tests/dashboard/test_i00044_chat_panel_layout.py` — new test file to review
- `tests/dashboard/test_code_layout_fixes.py` — established pattern reference

## Output Files

- `ai-dev/active/I-00044/reports/I-00044_S04_CodeReview_Tests_report.md`

## Review Checklist

### Coverage

- [ ] `TestBug2GridRowConstraint` class exists with at least 2 tests:
  - `test_page_body_has_grid_rows_1fr` — asserts exact class `lg:grid-rows-[1fr]` on `#page-body`
  - `test_page_body_grid_height_preserved` — asserts pre-existing classes still present
- [ ] `TestBug1CollapseToggleAffordance` class exists with at least 3 tests:
  - `test_toggle_tab_has_chat_label` — verifies "Chat" label is INSIDE the toggle tab subtree
  - `test_toggle_tab_has_aria_label_with_chat` — verifies aria-label on `#chat-toggle-tab`
  - `test_collapsed_state_is_not_bare_chevron_only` — verifies `#chat-toggle-tab` exists with icon/label
- [ ] `TestBug1KeyboardAccessibility` class exists with at least 2 tests:
  - `test_toggle_tab_is_a_button` — verifies element is `<button`
  - `test_mobile_elements_unchanged` — verifies mobile UI elements still present

### Semantic Correctness (CRITICAL — I003 Lesson)

- [ ] Tests check SPECIFIC values, not just presence:
  - BAD: `assert "grid-rows" in html` (too loose — matches anywhere)
  - GOOD: `assert "lg:grid-rows-[1fr]" in page_body_match.group(0)` (exact class on exact element)
- [ ] The "Chat" label test verifies the label is inside `#chat-toggle-tab`, not just
  anywhere in the rendered HTML (the header already has "Chat — Architecture" which would
  cause a false pass)
- [ ] The `test_collapsed_state_is_not_bare_chevron_only` test would FAIL against the
  pre-fix code (because `#chat-toggle-tab` did not exist before S01)

### Test Structure

- [ ] Follows the Jinja2 rendering pattern from `test_code_layout_fixes.py`:
  - `_template_dir()` helper
  - `jinja_env` fixture with all required stubbed filters (`intcomma`, `timeago`,
    `fmt_ts_time`, `localdt`) and globals (`url_for`, `is_db_stale`)
  - `mock_request` for templates that reference `request`
- [ ] Tests are in a `tests/dashboard/` file (not in `tests/unit/` or `tests/integration/`)
- [ ] No live DB connections — pure Jinja2 rendering
- [ ] No `pytest.mark.skip` or `xfail` on the new tests
- [ ] All new tests pass with `make test-unit`

### Reproduction Correctness

- [ ] `test_page_body_has_grid_rows_1fr` would FAIL against pre-S01 `project_code.html`
  (confirm by reading the pre-fix class list in the design document)
- [ ] `test_toggle_tab_has_chat_label` would FAIL against pre-S01 `panel.html`
  (the old panel had no `#chat-toggle-tab` element)

## Severity Guide

| Severity | Examples |
|----------|---------|
| CRITICAL | Test suite cannot run (import error, fixture broken) |
| HIGH | Missing test class; semantic check is actually a shape check; mobile regression test missing |
| MEDIUM | Test uses `assert "Chat" in html` without scoping to the toggle tab element |
| LOW | Minor naming nit; missing docstring |

## Output

Write to `ai-dev/active/I-00044/reports/I-00044_S04_CodeReview_Tests_report.md`.

End with: `APPROVED` / `APPROVED WITH NOTES` / `NEEDS REWORK`.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00044",
  "completion_status": "complete",
  "review_outcome": "APPROVED|APPROVED WITH NOTES|NEEDS REWORK",
  "critical_findings": 0,
  "high_findings": 0,
  "medium_findings": 0,
  "low_findings": 0,
  "blockers": [],
  "notes": ""
}
```
