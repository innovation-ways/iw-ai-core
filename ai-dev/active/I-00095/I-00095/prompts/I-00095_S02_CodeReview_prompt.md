# I-00095_S02_CodeReview_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies — `docs/IW_AI_Core_Agent_Constraints.md`. No alembic.

## Input Files

- `uv run iw item-status I-00095 --json`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/reports/I-00095_S01_Backend_report.md`
- `orch/auto_merge_aggregator.py` (post-S01)
- `tests/unit/test_auto_merge_aggregator.py` (post-S01)

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Whitelist semantics** — `SORTABLE_COLUMNS` contains exactly the
   four allowed columns (`created_at`, `event_type`, `entity_id`,
   `verdict`). NO `message`, NO arbitrary user-supplied column. SQL
   injection risk if any column name is interpolated as a raw string
   instead of using the `Column` object → CRITICAL.

2. **Direction validation** — only `"asc"` and `"desc"`. Any other
   value (case-mixed, padded, …) raises `ValueError`. CRITICAL if not.

3. **`NULLS LAST` on verdict sort** — verdict lives on the joined
   table; unverdicted rows have NULL. The design says NULLS LAST so
   the table is predictable in both directions. Verify with a code
   read.

4. **Backwards-compat** — existing callers (other test files in
   `tests/unit/test_auto_merge_aggregator.py` and the route handler
   pre-S03) still pass; new params have defaults that preserve the
   prior behaviour.

5. **No untyped `**kwargs`** — params are explicit, keyword-only
   (after `*`).

6. **RED evidence** — `tdd_red_evidence` in the report shows a
   plausible AssertionError, NOT an ImportError.

### TDD RED Evidence

Backend behavioural step — verify the report carries `tdd_red_evidence`
naming the new test and showing `AssertionError: Expected ascending …`.
Reason about whether the test would have failed against pre-S01 code
(it should — pre-S01 the function had no `sort` param at all, so the
test would raise `TypeError: unexpected keyword argument 'sort'` OR,
if the test author wrote it as a positional, return data in the wrong
order).

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_auto_merge_aggregator.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00095",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
