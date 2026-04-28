# I-00044_S05_CodeReview_Final_prompt

**Work Item**: I-00044 — Code View Chat Panel — Ugly Collapse State and Viewport Drift
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00044/I-00044_Issue_Design.md` — design document
- `ai-dev/active/I-00044/reports/I-00044_S01_Frontend_report.md`
- `ai-dev/active/I-00044/reports/I-00044_S02_CodeReview_Frontend_report.md`
- `ai-dev/active/I-00044/reports/I-00044_S03_Tests_report.md`
- `ai-dev/active/I-00044/reports/I-00044_S04_CodeReview_Tests_report.md`
- All modified source files:
  - `dashboard/templates/project_code.html`
  - `dashboard/templates/chat/panel.html`
  - `dashboard/static/chat/panel.js`
  - `dashboard/static/chat.css`
  - `dashboard/static/styles.css`
  - `tests/dashboard/test_i00044_chat_panel_layout.py`

## Output Files

- `ai-dev/active/I-00044/reports/I-00044_S05_CodeReview_Final_report.md`

## Review Scope

This is the global cross-layer review. Verify that all previous review findings were
addressed and that the overall change is complete, consistent, and correct.

### 1. Previous review findings resolved

- [ ] All CRITICAL/HIGH findings from S02 were resolved (check S02 report vs current code)
- [ ] All CRITICAL/HIGH findings from S04 were resolved (check S04 report vs current test file)

### 2. Bug 2 fix — completeness

- [ ] `#page-body` in `project_code.html` contains `lg:grid-rows-[1fr]`
- [ ] `base.html` was NOT modified — the fix is scoped to `project_code.html` only
- [ ] `code_architecture_view.html` was NOT modified — its `h-full overflow-y-auto` classes
  remain intact
- [ ] `dashboard/static/styles.css` includes the generated rule for `grid-template-rows: 1fr`
  at the `lg:` breakpoint (Tailwind JIT will emit it if `make css` was run)

### 3. Bug 1 fix — completeness

- [ ] `#chat-toggle-tab` button exists in `panel.html` with a chat icon SVG AND a rotated "Chat" label
- [ ] `#chat-collapse-btn` was removed or repurposed — there is NOT a second collapse button
  in the header alongside the new toggle tab
- [ ] `panel.js:applyCollapsedState()` updates both the panel's `data-collapsed` attribute
  and the toggle tab's `aria-label`
- [ ] Mobile behavior is intact: `#chat-close-btn`, `#chat-drawer-open`, `#chat-drawer-backdrop`
  are all present and unmodified
- [ ] Keyboard shortcut `Cmd+\` / `Ctrl+\` still triggers `togglePanel()`
- [ ] Resize handle wiring is unchanged

### 4. Test quality — reproduction and semantics

- [ ] Reproduction test `test_page_body_has_grid_rows_1fr` would FAIL against pre-fix code
- [ ] Reproduction test `test_toggle_tab_has_chat_label` would FAIL against pre-fix code
  (confirms tests are actually testing the fix, not just the presence of any HTML)
- [ ] No test uses a loose shape check (e.g. `"grid-rows" in html`) instead of a precise
  element-scoped assertion
- [ ] Mobile regression tests are present (`test_mobile_elements_unchanged`)

### 5. Acceptance criteria coverage

- [ ] **AC1** (collapsed chat recognisable): Covered by `test_toggle_tab_has_chat_label`,
  `test_collapsed_state_is_not_bare_chevron_only`, `test_toggle_tab_is_a_button`
- [ ] **AC2** (chat stays in viewport): Covered by `test_page_body_has_grid_rows_1fr`
  and `test_page_body_grid_height_preserved`
- [ ] **AC3** (regression test exists): All tests in `test_i00044_chat_panel_layout.py` pass

### 6. No scope creep

- [ ] No unrelated files modified
- [ ] No new Python dependencies added
- [ ] No changes to `orch/` layer, routers, or DB models

## Severity Guide

| Severity | Examples |
|----------|---------|
| CRITICAL | Mobile drawer broken; keyboard shortcut lost; `#page-body` still missing `lg:grid-rows-[1fr]` |
| HIGH | Two collapse buttons present; reproduction tests don't actually test pre-fix behaviour; `make css` not run |
| MEDIUM | Minor CSS scope issue; loose assertion that could pass on unrelated HTML |
| LOW | Cosmetic nit |

## Output

Write to `ai-dev/active/I-00044/reports/I-00044_S05_CodeReview_Final_report.md`.

End with: `APPROVED` / `APPROVED WITH NOTES` / `NEEDS REWORK`.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
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
