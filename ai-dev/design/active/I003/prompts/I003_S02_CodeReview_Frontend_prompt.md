# I003_S02_CodeReview_Frontend_prompt

**Work Item**: I003 — History Page Sorting Broken — Replace with Client-Side JS Sorting
**Step**: S02
**Agent**: CodeReview_Frontend

---

## Input Files

- `ai-dev/design/active/I003/I003_Issue_Design.md` — Design document
- `ai-dev/design/active/I003/reports/I003_S01_Frontend_report.md` — S01 report

## Output Files

- `ai-dev/design/active/I003/reports/I003_S02_CodeReview_Frontend_report.md` — Review report

## Context

You are reviewing the Frontend implementation for I003. The fix replaces server-side sorting (via `<a>` link page reloads) with client-side JavaScript sorting on the History page, matching the pattern used in the Batches page.

Read the design document and S01 report first, then read `CLAUDE.md`.

## Review Checklist

### 1. Sorting Pattern Consistency

- [ ] `sort_header` Jinja2 macro is fully removed
- [ ] Each `<th>` has `data-sort-key` and `onclick="sortTable('key')"` attributes
- [ ] SVG chevron icons are present in each sortable header
- [ ] Pattern matches `batches.html` (lines 41-54)

### 2. Data Attributes

- [ ] Each `<tr>` in `<tbody>` has `data-sort-*` attributes for all 6 columns
- [ ] `data-sort-duration` uses `-1` for null durations (not empty string)
- [ ] `data-sort-created_at` uses ISO format for correct string comparison
- [ ] `data-sort-id`, `data-sort-type`, `data-sort-title`, `data-sort-status` are present

### 3. JavaScript Implementation

- [ ] `sortTable()` function exists in an inline `<script>` block
- [ ] `isNumeric()` returns `true` for `duration`
- [ ] Sort direction toggles on repeated clicks
- [ ] SVG chevron opacity and rotation update correctly
- [ ] Uses `#history-table` selector (not `#batches-table`)
- [ ] Empty rows (`class="empty-row"`) are excluded from sorting

### 4. Pagination Removal

- [ ] All pagination HTML is removed (page links, prev/next buttons)
- [ ] Hidden inputs for `sort_by` and `sort_dir` are removed from filter form
- [ ] No `sort_by=` or `sort_dir=` in any remaining URLs
- [ ] Results count updated (no pagination range)

### 5. Filter Form Integrity

- [ ] Type, Status, Date From, Date To filters still work
- [ ] Filter form does NOT submit sort_by/sort_dir
- [ ] Clear link does NOT include sort params

### 6. No Regressions

- [ ] Row click navigation (`onclick="window.location=..."`) still works
- [ ] Status badges render correctly
- [ ] Duration formatting (Xh XXm, Xm XXs) preserved
- [ ] Empty state message still displays when no items match

## Severity Guide

- **CRITICAL**: Sorting doesn't work, data attributes missing, JS errors
- **HIGH**: Pattern diverges from batches page, pagination not removed
- **MEDIUM**: Minor styling differences, suboptimal JS
- **LOW**: Cosmetic, non-functional

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview_Frontend",
  "work_item": "I003",
  "completion_status": "complete",
  "findings": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
