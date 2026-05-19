# I-00095_S04_CodeReview_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step Being Reviewed**: S03 (api-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00095 --json`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/reports/I-00095_S03_Api_report.md`
- `dashboard/routers/auto_merge_ui.py` (post-S03)

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Query param shape** — both `sort` and `dir` are typed as `str`
   with defaults `"created_at"` and `"desc"`. Not `Literal[...]`
   (which would return 422 not 400).

2. **Whitelist validation** — invalid `sort` or `dir` raises
   `HTTPException(status_code=400, detail=…)`. Message is human-readable.

3. **Delegation** — values are passed through to
   `agg.list_recent_events(..., sort=sort, direction=dir)` without any
   string mangling.

4. **Template context** — `sort` and `direction` are added to the
   fragment context so S05's template can use them.

5. **No regression** — other route handlers (`auto_merge_event_detail`,
   `auto_merge_set_config`, `auto_merge_rollup`, `auto_merge_set_verdict`)
   are unchanged.

6. **dir is also forbidden as a Python builtin shadow only at module
   scope** — using `dir` as a parameter name shadows the builtin
   inside the function. The existing code uses `type: str | None`
   with `noqa: A002`; reuse the same pattern for `dir`.

### TDD RED Evidence

API step — `tdd_red_evidence = "n/a — API surface extension"`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00095",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
