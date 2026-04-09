# I003_S06_CodeReview_Tests_prompt

**Work Item**: I003 — History Page Sorting Broken — Replace with Client-Side JS Sorting
**Step**: S06
**Agent**: CodeReview_Tests

---

## Input Files

- `ai-dev/design/active/I003/I003_Issue_Design.md` — Design document
- `ai-dev/design/active/I003/reports/I003_S05_Tests_report.md` — S05 report

## Output Files

- `ai-dev/design/active/I003/reports/I003_S06_CodeReview_Tests_report.md` — Review report

## Context

You are reviewing the test implementation for I003. Tests verify that server-side sorting was removed and client-side JS sorting was added to the History page.

Read the design document and S05 report first, then read `CLAUDE.md`.

## Review Checklist

### 1. Reproduction Test Exists

- [ ] A test exists that would have FAILED before the fix
- [ ] It verifies `?sort_by=` and `?sort_dir=` are NOT in response HTML
- [ ] It verifies `sortTable` IS in response HTML

### 2. Semantic Correctness (CRITICAL)

- [ ] Tests verify SPECIFIC values, not just key existence
- [ ] Tests check specific `data-sort-*` attribute values against known test data
- [ ] Tests verify specific item IDs appear/don't appear (not just "non-empty")
- [ ] NO tests that only check `in data` or `len(data) > 0`

### 3. Coverage Completeness

- [ ] Client-side sort attributes on rows tested
- [ ] No pagination UI tested
- [ ] All items returned (no slicing) tested
- [ ] Backend function signature tested (no sort/page params)
- [ ] Filters still work tested
- [ ] sortTable JS presence tested

### 4. Test Isolation

- [ ] Unit tests don't touch the database
- [ ] Integration tests use testcontainers (not live DB)
- [ ] Tests don't depend on each other's state
- [ ] Test data is created within each test (not shared fixtures that could break)

### 5. Conventions

- [ ] Tests follow project naming conventions
- [ ] Tests are in correct directories (unit vs integration)
- [ ] Fixtures match project patterns

## Severity Guide

- **CRITICAL**: Tests only check shape not semantics, reproduction test missing
- **HIGH**: Missing coverage area, tests hit live DB
- **MEDIUM**: Test isolation issues
- **LOW**: Naming, organization

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview_Tests",
  "work_item": "I003",
  "completion_status": "complete",
  "findings": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
