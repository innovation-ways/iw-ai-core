# I-00046_S05_CodeReview_Final_prompt

**Work Item**: I-00046 — Code view chat panel — toggle button clipped and viewport drift on module select
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01, S03

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state**: `uv run iw item-status I-00046 --json`
- `ai-dev/active/I-00046/I-00046_Issue_Design.md` — design document
- `ai-dev/active/I-00046/reports/I-00046_S01_Frontend_report.md`
- `ai-dev/active/I-00046/reports/I-00046_S02_CodeReview_Frontend_report.md`
- `ai-dev/active/I-00046/reports/I-00046_S03_Tests_report.md`
- `ai-dev/active/I-00046/reports/I-00046_S04_CodeReview_Tests_report.md`
- `dashboard/templates/project_code.html`
- `dashboard/templates/chat/panel.html`
- `tests/dashboard/test_chat_panel_layout_i00046.py`

## Output Files

- `ai-dev/active/I-00046/reports/I-00046_S05_CodeReview_Final_report.md`

## Context

This is the global review of all work done for I-00046. Two bugs were fixed:

- **Bug (a)**: Toggle button clipped by `overflow-hidden` on aside + duplicate ID in panel.html
- **Bug (c)**: Page height grows unboundedly when a module is loaded — `#code-content-root`
  lacked `min-h-0`

Verify the fix is complete, minimal in scope, and correctly tested.

## Review Checklist

### 1. Fix completeness

- [ ] Bug (a): `<aside id="chat-panel-slot">` no longer has `overflow-hidden`
- [ ] Bug (a): `<aside id="chat-panel-slot">` has `lg:min-h-0`
- [ ] Bug (a): `panel.html`'s inner wrapper no longer has `id="chat-panel-slot"`
- [ ] Bug (a): Inner wrapper has `relative flex-1 min-h-0`
- [ ] Bug (c): `#code-content-root` has `class="lg:min-h-0"`

### 2. No regressions introduced

- [ ] Existing I-00033 tests still pass (`test_code_layout_fixes.py`)
- [ ] The architecture card (`code_architecture_view.html`) is unchanged — its
  `overflow-y-auto h-full` remains the scroll container for the content column
- [ ] `panel.js` is unchanged — collapse/expand behaviour driven by `#chat-toggle-tab`
  click handler is unaffected
- [ ] The CSS collapse rules in `panel.html`'s `<style>` block correctly target elements
  inside `#chat-panel` (structural change to wrapper div does not break selector)

### 3. Scope discipline

- [ ] No refactoring beyond the three targeted HTML attribute changes
- [ ] No JS changes
- [ ] No migration or DB changes

### 4. Reproduction tests verify semantic correctness

- [ ] Tests assert on the **specific element's opening tag**, not the whole page
- [ ] `test_no_duplicate_chat_panel_slot_id` counts exact occurrences of the ID string
- [ ] `test_aside_does_not_have_overflow_hidden` reads the `<aside>` tag specifically
- [ ] `test_code_content_root_has_min_h_0` reads the `#code-content-root` tag specifically
- [ ] Tests include descriptive failure messages with `I-00046` reference

### 5. Prior review findings resolved

- [ ] All CRITICAL and HIGH findings from S02 and S04 are addressed
- [ ] Mandatory fix count from both reviews is 0 (or all fixes were applied)

### 6. CSS rebuild

- [ ] If `make css` was run (new Tailwind classes added), the report confirms which
  classes were new, and `dashboard/static/styles.css` is staged
- [ ] If `make css` was NOT needed (all classes pre-existed), the report confirms this

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Breaks functionality, data loss, security | Must fix before merge |
| HIGH | Bug not actually fixed, missing requirement, architectural violation | Must fix |
| MEDIUM (fixable) | Quality issue | Fix in cycle |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00046",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
