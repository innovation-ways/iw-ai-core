# I-00046_S02_CodeReview_Frontend_prompt

**Work Item**: I-00046 — Code view chat panel — toggle button clipped and viewport drift on module select
**Step Being Reviewed**: S01 (Frontend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this fix.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00046 --json`
- `ai-dev/active/I-00046/I-00046_Issue_Design.md` — design document
- `ai-dev/active/I-00046/reports/I-00046_S01_Frontend_report.md` — S01 implementation report
- `dashboard/templates/project_code.html` — modified by S01
- `dashboard/templates/chat/panel.html` — modified by S01
- `dashboard/static/styles.css` — may have been rebuilt by S01

## Output Files

- `ai-dev/active/I-00046/reports/I-00046_S02_CodeReview_Frontend_report.md`

## Context

Review the template fixes applied in S01 for the two layout bugs:

- **Bug (a)**: Toggle button invisible — `overflow-hidden` clipped it; duplicate
  `id="chat-panel-slot"` was introduced by I-00044
- **Bug (c)**: Page grows beyond viewport on module select — `#code-content-root` lacked
  `min-h-0` for CSS Grid containment

## Review Checklist

### 1. Bug (a) — Toggle button fix

Verify in `dashboard/templates/project_code.html`:
- [ ] `<aside id="chat-panel-slot">` does NOT contain `overflow-hidden` in its class list
- [ ] `<aside id="chat-panel-slot">` has `lg:min-h-0` in its class list
- [ ] The ID `chat-panel-slot` appears exactly ONCE in the rendered output (no duplicate)

Verify in `dashboard/templates/chat/panel.html`:
- [ ] The outer wrapper div (line ~9) does NOT have `id="chat-panel-slot"`
- [ ] The outer wrapper div has `relative flex-1 min-h-0` classes
- [ ] The toggle button (`#chat-toggle-tab`) is still present with `style="left: -48px"`
  and `absolute top-1/2 -translate-y-1/2` classes
- [ ] The `<style>` block with CSS collapse rules is still present and unchanged

### 2. Bug (c) — Content root containment fix

Verify in `dashboard/templates/project_code.html`:
- [ ] `#code-content-root` div has `class="lg:min-h-0"` (or a class attribute that
  includes `lg:min-h-0`)
- [ ] No other classes were added or removed from `#code-content-root`

### 3. CSS rebuild

- [ ] If new Tailwind classes were introduced, `dashboard/static/styles.css` was rebuilt
  via `make css` and the change is in the report
- [ ] If no new classes were needed, the report confirms that

### 4. Scope adherence

- [ ] `dashboard/static/chat/panel.js` was NOT modified (dead code `panelSlot` left as-is)
- [ ] No other template or CSS file was changed beyond what the design specifies
- [ ] The existing `test_code_layout_fixes.py` tests still pass (I-00033 not regressed)

### 5. CSS correctness

Inspect the collapse CSS rules in `panel.html`:
```css
#chat-panel[data-collapsed="true"] #chat-context-label,
#chat-panel[data-collapsed="true"] #chat-messages,
...
```
These must still correctly target elements inside `#chat-panel`. Confirm the structural
change (removing the wrapper's duplicate ID) does not break this selector chain.

### 6. Security / XSS

No user input is touched in this fix — only static class attribute changes. No security
concerns expected; confirm no interpolated values were introduced.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Breaks functionality, data loss, security | Must fix before merge |
| HIGH | Significant bug, missing requirement | Must fix before merge |
| MEDIUM (fixable) | Code quality, convention violation | Fix in fix cycle |
| MEDIUM (suggestion) | Better pattern available | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00046",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
