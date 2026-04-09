# I003_S04_CodeReview_Backend_prompt

**Work Item**: I003 — History Page Sorting Broken — Replace with Client-Side JS Sorting
**Step**: S04
**Agent**: CodeReview_Backend

---

## Input Files

- `ai-dev/design/active/I003/I003_Issue_Design.md` — Design document
- `ai-dev/design/active/I003/reports/I003_S03_Backend_report.md` — S03 report

## Output Files

- `ai-dev/design/active/I003/reports/I003_S04_CodeReview_Backend_report.md` — Review report

## Context

You are reviewing the Backend cleanup for I003. The changes remove server-side sorting and pagination from `project_pages.py` since sorting is now handled client-side by JavaScript.

Read the design document and S03 report first, then read `CLAUDE.md`.

## Review Checklist

### 1. Dead Code Removal

- [ ] `_SORT_COLUMNS` dict is removed
- [ ] `_ALLOWED_SORT_BY` set is removed
- [ ] `_ALLOWED_SORT_DIR` tuple is removed
- [ ] `nulls_first`/`nulls_last` imports removed (if unused elsewhere)
- [ ] No remaining references to `sort_by` or `sort_dir` in the file

### 2. `_history_items()` Signature

- [ ] `sort_by` parameter removed
- [ ] `sort_dir` parameter removed
- [ ] `page` parameter removed
- [ ] Function still returns `(list[HistoryItem], int)` tuple
- [ ] A sensible default ORDER BY is applied (e.g., `created_at DESC`)

### 3. `_history_items()` Body

- [ ] Sort validation block removed
- [ ] Dynamic sort logic removed (the `if sort_by == "duration"` branch)
- [ ] Pagination slicing removed (no `offset`, no `page_rows`)
- [ ] All matching items are returned
- [ ] Filter logic (type, status, date range) still intact

### 4. `project_history()` Route

- [ ] `page`, `sort_by`, `sort_dir` removed from route params
- [ ] `total_pages` calculation removed
- [ ] Template context does not include `page`, `total_pages`, `page_size`, `sort_by`, `sort_dir`
- [ ] Template context still includes all filter-related vars

### 5. No Regressions

- [ ] Existing unit tests still pass
- [ ] `HistoryItem` dataclass unchanged
- [ ] `_HISTORY_PAGE_SIZE` can be removed if no longer referenced
- [ ] Type annotations are correct (mypy strict)

## Severity Guide

- **CRITICAL**: Sort/page params still accepted, broken query
- **HIGH**: Dead code not removed, imports still present
- **MEDIUM**: Minor cleanup missed
- **LOW**: Cosmetic

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview_Backend",
  "work_item": "I003",
  "completion_status": "complete",
  "findings": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
