# CR-00013_S04_CodeReview_prompt

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` — Design
- `ai-dev/active/CR-00013/reports/CR-00013_S03_Backend_report.md` — S03 report
- All files in S03's `files_changed`

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S04_CodeReview_report.md` — review report

## Context

Review S03: five N+1 query rewrites on dashboard entry-point routes. The bar is bounded query counts independent of N, while preserving the exact rendered output.

## Review Checklist

### 1. Bounded Queries (Primary Goal)

- For each of C1–C5, confirm the rewrite issues a constant number of queries regardless of N. Trace the code path end-to-end.
- Confirm no hidden lazy-loads inside the template layer (check the corresponding Jinja templates for `{{ obj.relationship_name }}` accesses that would trigger a DB hit).
- Query-count tests exist and fail on pre-S03 code (ask the agent to run the test on a reverted copy if unsure).

### 2. Semantic Correctness

- Aggregation queries produce the same counts as the original loop. `COUNT(*)` vs `COUNT(column)` can differ on NULLs — check.
- `DISTINCT ON (step_id) ... ORDER BY step_id, created_at DESC` (PostgreSQL) returns the latest run; confirm the order clause is correct (DESC on the timestamp).
- Composite-PK `IN` clauses use `tuple_()` correctly (or an equivalent that doesn't collapse `(p1, w1)` with `(p2, w1)`).
- Return shapes unchanged — templates still receive objects with the same attributes.

### 3. Project Conventions

- SQLAlchemy 2.0 style (`select(...)`, `.where()`, `.scalars()`).
- No raw `.query(...)` legacy API.
- Composite-PK awareness (`work_items`, `batch_items`).
- Imports organized.

### 4. Regressions

- Pages C1–C5 visit: `/`, `/project/{pid}`, `/project/{pid}/batch/{bid}`, `/project/{pid}/item/{iid}` (all tabs), `/system/running`. All must still render correctly with the right counts, orderings, and null-handling.
- No changes leaked to adjacent routes not listed in scope.

### 5. Security

- No SQL injection (use parameterized queries; no f-strings in `text(...)`).
- No unauthorized data exposure (the rewritten queries should still be scoped by `project_id` where relevant).

### 6. Testing

- One regression test per hotspot using a query-count fixture.
- Tests assert bound holds for N in {0, 1, 10}.
- Tests use the testcontainer fixture; no live-DB connections.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `make quality`

## Severity Levels

(Same table as S02.)

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00013",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
