# I-00045_S05_CodeReview_Final_prompt

**Work Item**: I-00045 — OSS Status Widget and Page: Ugly Layout and Raw JSON Rendering
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits / Migrations policy

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Input Files

- Design document: `ai-dev/active/I-00045/I-00045_Issue_Design.md`
- S01 report: `ai-dev/active/I-00045/reports/I-00045_S01_Frontend_report.md`
- S02 report: `ai-dev/active/I-00045/reports/I-00045_S02_CodeReview_Frontend_report.md`
- S03 report: `ai-dev/active/I-00045/reports/I-00045_S03_Tests_report.md`
- S04 report: `ai-dev/active/I-00045/reports/I-00045_S04_CodeReview_Tests_report.md`
- All changed files:
  - `dashboard/templates/fragments/oss_status_frame.html`
  - `dashboard/templates/pages/project/oss.html`
  - `dashboard/static/styles.css`
  - `tests/dashboard/test_oss_status_rendering.py`

## Output Files

- `ai-dev/active/I-00045/reports/I-00045_S05_CodeReview_Final_report.md`

---

## Context

Global cross-agent review for I-00045. Verify that all five defects are fixed consistently, the tests are semantically correct, and no regressions were introduced.

Read `dashboard/CLAUDE.md` and `tests/CLAUDE.md` before reviewing.

---

## Review Checklist

### Fix Completeness

- [ ] **AC1** — Dashboard pill shows formatted summary ("N passed · N critical · N warnings"); no raw dict markers in HTML
- [ ] **AC2** — "OSS STATUS" heading is an `<a>` linking to `/project/{id}/oss`
- [ ] **AC3** — Stale warning has no border (`border border-warning/30` removed); background tint retained
- [ ] **AC4** — OSS page uses CSS-styled dots (not 🔴/🟡/🟢 emoji) for status indicator
- [ ] **AC5** — Reproduction + regression tests exist and are semantically correct

### Test Semantic Correctness (I003 Lesson)

- [ ] Reproduction test (`test_i00045_oss_widget_no_raw_json`) explicitly checks for the ABSENCE of raw dict text — it would have failed against pre-fix code
- [ ] Count test asserts specific strings like `"50 passed"` not just `"passed"`
- [ ] Emoji test asserts specific characters `🔴`, `🟡`, `🟢` are absent
- [ ] Heading link test asserts the href value, not just the presence of an `<a>` tag

### Consistency

- [ ] The new CSS dots in `oss.html` match the style of the existing summary stats card dots (same Tailwind classes, same sizing)
- [ ] The "OSS Status" link styling is consistent with other heading-level links in the dashboard
- [ ] `make css` was run — `dashboard/static/styles.css` contains any new Tailwind classes used

### No Scope Creep

- [ ] No unrelated templates, Python files, or CSS were modified
- [ ] No new abstractions or helper functions were introduced beyond what the fix required
- [ ] The `oss_status_pill.html` fragment (used elsewhere) was NOT modified — this fix targets `oss_status_frame.html` only

### Open CRITICAL/HIGH Findings from Previous Reviews

- [ ] All CRITICAL findings from S02 and S04 reports have been resolved
- [ ] All HIGH findings from S02 and S04 reports have been resolved or explicitly deferred with justification

---

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
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

Set `approved: true` if there are no CRITICAL or HIGH findings across all steps.
