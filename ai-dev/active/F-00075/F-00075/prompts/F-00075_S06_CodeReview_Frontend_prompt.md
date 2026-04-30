# F-00075_S06_CodeReview_Frontend_prompt

**Work Item**: F-00075 -- MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)
**Step**: S06
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits / Migrations off-limits

(Same policy as in S01.)

## Input Files

- `ai-dev/active/F-00075/F-00075_Feature_Design.md`
- `ai-dev/active/F-00075/reports/F-00075_S04_Frontend_report.md`
- `dashboard/templates/fragments/llm_usage_footer.html` (post-S04)
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00075/reports/F-00075_S06_CodeReview_Frontend_report.md`

## Context

Per-agent code review of S04 (frontend template).

## Requirements — Review Checklist

### Correctness

- [ ] The MiniMax label uses `{{ minimax_reset or '5h' }}`, mirroring Claude.
- [ ] When `minimax_reset` is truthy (e.g. `"2h 43m"`), the label renders that string. When `None`, falls back to literal `"5h"`.
- [ ] The optional tooltip uses Jinja's `is not none` guard for both `minimax_5h_used` and `minimax_5h_total` so the failure path does not produce `"None / None requests"`.
- [ ] When the tooltip renders, format is `"{used} / {total} requests"`.

### CSS / Tailwind safety

- [ ] No new Tailwind utility class strings introduced. If any were added, `make css` was run and the regenerated `dashboard/static/styles.css` is included in the change set.
- [ ] No dynamically constructed class strings (Tailwind JIT cannot purge those safely).

### Layout / accessibility

- [ ] No new ARIA / accessibility regressions vs the previous fragment.
- [ ] The change does not alter the `hx-target` swap structure in a way that breaks the existing 60s htmx polling cycle.

### No regression to Claude

- [ ] The Claude row in the same template is byte-identical to `main`.

### Tests

- [ ] If `tests/dashboard/test_chat_templates.py` or any other test asserts on this fragment's HTML, it has been updated. Otherwise S07 will add coverage.
- [ ] `make test-unit` passes after the change.

## Output

Write `F-00075_S06_CodeReview_Frontend_report.md` with:

- Pass/fail per checklist item.
- Severity-tagged findings.
- `approve` or `request_changes`.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00075",
  "completion_status": "complete",
  "review_outcome": "approve|request_changes",
  "findings": [],
  "tests_passed": true,
  "notes": ""
}
```
