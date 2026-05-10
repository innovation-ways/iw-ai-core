# CR-00042_S04_CodeReview_prompt

**Work Item**: CR-00042 — Fix Broken "Open full docs" Links in Help Popups
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/CR-00042/CR-00042_CR_Design.md` — acceptance criteria
- `dashboard/templates/_partials/help/*.html` — all 22 updated partials
- `ai-dev/active/CR-00042/reports/CR-00042_S03_frontend-impl_report.md` — S03 report

## Output Files

- `ai-dev/active/CR-00042/reports/CR-00042_S04_code_review_report.md` — findings with severities

## Review Checklist

### Critical checks

- [ ] All 22 help partial files have been updated (count the modified files)
- [ ] Zero occurrences of `href="/docs/` in `dashboard/templates/_partials/help/` (run grep)
- [ ] Zero occurrences of `href="/orch/` in `dashboard/templates/_partials/help/` (run grep)
- [ ] Every updated link uses exactly `href="{{ docs_link }}"` (Jinja2 variable, not a literal string)

### High checks

- [ ] Link text `Open full docs →` is unchanged in all 22 files
- [ ] CSS class `help-content__docs-link` is unchanged in all 22 files
- [ ] No other content in the partials has been modified (only the `href` attribute changed)
- [ ] All 22 slugs from `_SLUG_TO_DOC` in `help.py` correspond to actual partial filenames

### Medium checks

- [ ] HTML structure of each partial is well-formed (no unclosed tags introduced)
- [ ] `projects.html` partial updated (it links from the landing page, easy to miss)

### Low checks

- [ ] No extra whitespace or encoding artifacts introduced in any file

## Severity Guide

- **CRITICAL**: Any partial still has a hardcoded broken href; `docs_link` variable missing
- **HIGH**: Link text or CSS class changed; non-href content modified unintentionally
- **MEDIUM**: A partial missed; malformed HTML
- **LOW**: Whitespace changes

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00042",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00042/reports/CR-00042_S04_code_review_report.md"
  ],
  "blockers": [],
  "notes": ""
}
```
