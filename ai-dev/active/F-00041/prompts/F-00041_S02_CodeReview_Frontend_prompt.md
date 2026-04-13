# F-00041_S02_CodeReview_Frontend_prompt

**Work Item**: F-00041 — Interactive Document IDE — Guide Editor & Diff Viewer UI
**Step**: S02
**Agent**: CodeReview_Frontend
**Parallel With**: None — review of S01

---

## Input Files

- `ai-dev/active/F-00041/F-00041_Feature_Design.md` — Design document
- `ai-dev/active/F-00041/reports/F-00041_S01_Frontend_report.md` — S01 report
- `dashboard/templates/docs_detail.html` — Modified page
- `dashboard/routers/docs.py` — New endpoints
- All 5 new template fragments

## Output Files

- `ai-dev/active/F-00041/reports/F-00041_S02_CodeReview_Frontend_report.md`

## Context

Review the frontend implementation of F-00041.

## Review Checklist

### Correctness
- [ ] IDE tab lazy-loads via `hx-trigger="click once"` — not rendered on page load
- [ ] All 9 endpoints present in `dashboard/routers/docs.py`
- [ ] POST endpoints read `guide_md` from Form body
- [ ] DELETE endpoints return 204 or HTML fragment (not redirect)
- [ ] Section guide panel derives sections from `extract_sections(doc.content)` at render time
- [ ] "No H2 headings" message shown when sections = ["Document"]
- [ ] Instance guide shows "Inheriting from type guide" when no override exists
- [ ] Section diff panel loads from `/diff/sections` JSON endpoint

### Conventions
- [ ] Fragments do NOT extend `base.html`
- [ ] No inline JavaScript — htmx only
- [ ] No hardcoded project_id or doc_id — all from template context
- [ ] No dynamic Tailwind class construction (avoid f-string class names)
- [ ] Thin router pattern — all guide logic delegated to `DocService`

### UX
- [ ] Save button gives user feedback (toast or in-place update)
- [ ] Error states handled (DB error → error toast, not silent failure)
- [ ] Section guides list is scrollable if many sections

### Architecture
- [ ] No direct DB access in router — all through `DocService`
- [ ] `extract_sections` imported from `orch.doc_sections` in the router

## Severity Classification

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview_Frontend",
  "work_item": "F-00041",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```
