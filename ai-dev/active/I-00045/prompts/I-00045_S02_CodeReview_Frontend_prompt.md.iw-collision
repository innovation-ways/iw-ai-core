# I-00045_S02_CodeReview_Frontend_prompt

**Work Item**: I-00045 — OSS Status Widget and Page: Ugly Layout and Raw JSON Rendering
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits / Migrations policy

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Input Files

- Design document: `ai-dev/active/I-00045/I-00045_Issue_Design.md`
- S01 report: `ai-dev/active/I-00045/reports/I-00045_S01_Frontend_report.md`
- Modified template: `dashboard/templates/fragments/oss_status_frame.html`
- Modified template: `dashboard/templates/pages/project/oss.html`
- Regenerated CSS: `dashboard/static/styles.css`

## Output Files

- `ai-dev/active/I-00045/reports/I-00045_S02_CodeReview_Frontend_report.md`

---

## Context

Review the S01 Frontend implementation for I-00045. This step fixed five cosmetic defects in two Jinja2 templates. Focus on correctness of the rendering logic and consistency with the existing UI patterns.

Read `dashboard/CLAUDE.md` for conventions before reviewing.

---

## Review Checklist

### 1. Raw JSON fix (AC1)

- [ ] `{{ scan_summary.summary }}` is no longer rendered directly anywhere in `oss_status_frame.html`
- [ ] The pill label computes `passed`, `critical`, `warnings` from the dict keys `must_pass + should_pass + may_pass`, `must_fail`, `should_fail` respectively
- [ ] Dict key access uses `.get(key, 0)` or equivalent to avoid `NoneType` errors if a key is absent
- [ ] The formatted label "N passed · N critical · N warnings" appears in the expected location inside the pill `<a>` element
- [ ] "critical" segment is omitted when `must_fail == 0`; "warnings" segment is omitted when `should_fail == 0`

### 2. Clickable heading (AC2)

- [ ] "OSS STATUS" / "OSS Status" heading is now an `<a>` element linking to `/project/{{ current_project.id }}/oss`
- [ ] The link is rendered unconditionally (not gated on `oss_enabled`)
- [ ] The link uses Tailwind hover styles consistent with other nav links in the dashboard

### 3. Rescan button relocation

- [ ] The old `<button>Rescan</button>` that was inline with the pill has been removed
- [ ] A refresh action (button or icon) is now in the heading row
- [ ] The htmx behaviour (`hx-get`, `hx-swap`, `hx-target`) is preserved on the refresh action

### 4. Stale warning border (AC3)

- [ ] `border border-warning/30` is removed from the stale banner `class=` in `oss_status_frame.html`
- [ ] `bg-warning/10` and `text-warning` are preserved
- [ ] The stale warning is still visible and accessible (not invisible)

### 5. OSS page emoji replacement (AC4)

- [ ] In `oss.html`, `🔴`, `🟡`, `🟢` emoji are replaced with CSS-styled dots
- [ ] The inline stale `⚠` emoji inside the pill is also replaced (SVG or removed in favour of the stale banner)
- [ ] New CSS dots use `bg-red-500`, `bg-amber-500`, `bg-emerald-500` (or equivalent) — consistent with existing summary stats card

### 6. CSS regeneration

- [ ] `dashboard/static/styles.css` was regenerated (`make css` was run)
- [ ] Any new Tailwind classes used in templates appear in the compiled CSS

### 7. No regressions

- [ ] The `{% if not oss_enabled %}` / `{% elif running_job %}` / `{% else %}` branches in `oss_status_frame.html` are untouched beyond the specific fix points
- [ ] The OSS page table, filter tabs, and finding modals are not modified
- [ ] No new Python, JS, or CSS files were created (fix is template-only)

---

## Severity Scale

- **CRITICAL**: The raw JSON still appears in rendered HTML; the heading link is missing; would fail AC1/AC2
- **HIGH**: Dict key access could raise `KeyError` or `TypeError` on a partial `summary_json`; CSS not regenerated
- **MEDIUM**: Heading link missing hover/focus styles; stale banner still has a faint border
- **LOW**: Minor whitespace or indentation issues in the template

---

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00045",
  "completion_status": "complete|partial|blocked",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "file:line",
      "description": "What is wrong",
      "suggestion": "How to fix"
    }
  ],
  "approved": true,
  "notes": ""
}
```

Set `approved: true` if there are no CRITICAL or HIGH findings. List all findings regardless.
