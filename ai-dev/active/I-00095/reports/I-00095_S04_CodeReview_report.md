# I-00095 — S04 Code Review Report (Reviewing S03 api-impl)

## Scope Reviewed

- Design: `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- Implementation report: `ai-dev/active/I-00095/reports/I-00095_S03_Api_report.md`
- Code under review: `dashboard/routers/auto_merge_ui.py`

## What was reviewed

Validated S03 against the step checklist:

1. **Query param shape**: `sort` and `dir` are typed as `str` with defaults `"created_at"` and `"desc"`.
2. **Whitelist validation**: both params are validated with explicit allowlists and invalid values raise `HTTPException(status_code=400, detail=...)` with human-readable details.
3. **Delegation**: values are passed directly to `agg.list_recent_events(..., sort=sort, direction=dir)` without mangling.
4. **Template context**: `sort` and `direction` are included in fragment context.
5. **No regression**: no changes to unrelated handlers (`auto_merge_event_detail`, `auto_merge_set_config`, `auto_merge_rollup`, `auto_merge_set_verdict`) in the reviewed diff.
6. **`dir` shadowing pattern**: used as function parameter with `# noqa: A002`, matching project pattern.

## Quality gates run

- `make lint` ✅
- `make format` ✅ (`ruff format --check` reported already formatted)

## Test verification

- Command required by step executed:
  - `uv run pytest tests/dashboard/test_auto_merge_routes.py -v`
- Result:
  - Test cases: **51 passed, 0 failed**
  - Process exit: non-zero due to repo-wide coverage fail-under gate (20.07% < 50%), not due to route failures.

## Findings

No mandatory fixes found for S03 scope.

## TDD RED Evidence

`n/a — API surface extension`

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00095",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "uv run pytest tests/dashboard/test_auto_merge_routes.py -v => 51 passed, 0 failed; command exited non-zero only because global coverage fail-under (20.07% < 50%).",
  "notes": "S03 implementation matches design/checklist for route-level sort/dir API extension."
}
```
