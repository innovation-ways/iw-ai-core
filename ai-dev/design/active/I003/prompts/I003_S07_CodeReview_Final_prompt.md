# I003_S07_CodeReview_Final_prompt

**Work Item**: I003 — History Page Sorting Broken — Replace with Client-Side JS Sorting
**Step**: S07
**Agent**: CodeReview_Final

---

## Input Files

- `ai-dev/design/active/I003/I003_Issue_Design.md` — Design document
- `ai-dev/design/active/I003/reports/I003_S01_Frontend_report.md` — S01 report
- `ai-dev/design/active/I003/reports/I003_S02_CodeReview_Frontend_report.md` — S02 review
- `ai-dev/design/active/I003/reports/I003_S03_Backend_report.md` — S03 report
- `ai-dev/design/active/I003/reports/I003_S04_CodeReview_Backend_report.md` — S04 review
- `ai-dev/design/active/I003/reports/I003_S05_Tests_report.md` — S05 report
- `ai-dev/design/active/I003/reports/I003_S06_CodeReview_Tests_report.md` — S06 review

## Output Files

- `ai-dev/design/active/I003/reports/I003_S07_CodeReview_Final_report.md` — Global review report

## Context

You are performing the global code review for I003. This incident replaced server-side sorting (page reloads) with client-side JavaScript sorting on the History page, removed pagination, and cleaned up the backend.

Review ALL changes across all agents for consistency, correctness, and completeness.

## Review Checklist

### 1. Frontend ↔ Backend Consistency

- [ ] Frontend template does NOT reference `sort_by`, `sort_dir`, `page`, `total_pages`, `page_size` from template context
- [ ] Backend does NOT pass `sort_by`, `sort_dir`, `page`, `total_pages`, `page_size` to template context
- [ ] Template variables used in Jinja2 match what the backend provides
- [ ] No broken template rendering (missing variables, wrong names)

### 2. Sorting Implementation Completeness

- [ ] All 6 columns are sortable: ID, Type, Title, Status, Date, Duration
- [ ] `data-sort-*` attributes exist on every `<tr>` for all 6 columns
- [ ] `sortTable()` JS function handles all column types correctly
- [ ] Numeric sorting for `duration`, string sorting for others
- [ ] Sort direction toggles work
- [ ] Visual indicators (SVG chevrons) update correctly

### 3. Pagination Fully Removed

- [ ] No `page` param in route handler
- [ ] No `_HISTORY_PAGE_SIZE` usage (can be removed if unused elsewhere)
- [ ] No pagination HTML in template
- [ ] No `page=` in any URL in the template
- [ ] `_history_items()` returns all items

### 4. Filter System Intact

- [ ] Type filter still works
- [ ] Status filter still works
- [ ] Date range filter still works
- [ ] Clear filter link works
- [ ] Filter form submits correctly (no stale hidden inputs)

### 5. Test Coverage

- [ ] Reproduction test exists and targets the correct scenario
- [ ] Tests verify SEMANTIC correctness (specific values, not just shape)
- [ ] All acceptance criteria from design doc are covered
- [ ] Tests don't connect to live database

### 6. Design Document Compliance

- [ ] All acceptance criteria met (AC1-AC5)
- [ ] No scope creep (only sorting fix, no extra features)
- [ ] Files changed match what was planned

### 7. CLAUDE.md Compliance

- [ ] Ruff line-length 100
- [ ] mypy strict passes
- [ ] No hardcoded values
- [ ] Test isolation (testcontainers)

## Severity Guide

- **CRITICAL**: Template/backend mismatch causing runtime errors, sorting broken
- **HIGH**: Missing coverage, dead code remaining, filter broken
- **MEDIUM**: Minor inconsistencies
- **LOW**: Cosmetic

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I003",
  "completion_status": "complete",
  "findings": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
