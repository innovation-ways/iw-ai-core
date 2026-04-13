# F-00041_S04_CodeReview_Final_prompt

**Work Item**: F-00041 — Interactive Document IDE — Guide Editor & Diff Viewer UI
**Step**: S04
**Agent**: CodeReview_Final
**Parallel With**: None — final review of all work

---

## Input Files

- `ai-dev/active/F-00041/F-00041_Feature_Design.md` — Design document
- `ai-dev/active/F-00041/reports/F-00041_S01_Frontend_report.md`
- `ai-dev/active/F-00041/reports/F-00041_S02_CodeReview_Frontend_report.md`
- `ai-dev/active/F-00041/reports/F-00041_S03_Tests_report.md`
- `dashboard/templates/docs_detail.html`
- `dashboard/routers/docs.py`
- All 5 new template fragments
- `tests/integration/api/test_docs_ide_api.py`

## Output Files

- `ai-dev/active/F-00041/reports/F-00041_S04_CodeReview_Final_report.md`

## Context

Global review of all F-00041 work. Evaluate completeness and UX correctness.

## Review Checklist

### Completeness (all 5 ACs from design doc)
- [ ] AC1: IDE tab loads on document detail page (lazy htmx load)
- [ ] AC2: Type guide editor shows and saves content
- [ ] AC3: Instance guide shows "Inheriting" message when no override
- [ ] AC4: Section guide panel lists sections from doc content
- [ ] AC5: Section diff panel shows changed sections with status

### Correctness
- [ ] All 9 endpoints present and tested
- [ ] IDE tab is lazy-loaded (not rendered on initial page load)
- [ ] `extract_sections` used for section list (not a DB query)
- [ ] All endpoints use `DocService` methods — no direct DB access in router
- [ ] Existing tabs on `docs_detail.html` are unaffected

### UX
- [ ] Save operations give user feedback (form swaps to show updated state)
- [ ] Delete operations handle "not found" gracefully (204 or cleared state)
- [ ] Section list scrolls if many sections

### Integration
- [ ] Type guide uses F-00037 service methods
- [ ] Instance guide uses F-00038 service methods
- [ ] Section guides use F-00039 service methods
- [ ] Diff panel loads from F-00040 `/diff/sections` endpoint

## Severity Classification

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview_Final",
  "work_item": "F-00041",
  "completion_status": "complete",
  "review_passed": true,
  "findings": [],
  "mandatory_fixes": [],
  "notes": ""
}
```
