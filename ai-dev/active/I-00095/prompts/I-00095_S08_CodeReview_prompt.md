# I-00095_S08_CodeReview_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00095 --json`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/reports/I-00095_S07_Tests_report.md`
- `tests/unit/test_auto_merge_aggregator.py` (post-S07)
- `tests/dashboard/test_auto_merge_routes.py` (post-S07)

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S08_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Test placement (I-00067)**:
   - Unit tests under `tests/unit/test_auto_merge_aggregator.py`.
   - Dashboard tests under `tests/dashboard/test_auto_merge_routes.py`.

2. **Semantic correctness (I003)**:
   - Sort-order assertions compare full lists, not just "non-empty".
   - The "rejects unknown" tests assert the exact error message via
     `pytest.raises(..., match=...)` rather than just `pytest.raises`.
   - Chevron / aria-sort asserted with specific element scoping (not
     bare substring on full HTML).

3. **Coverage** — the design's named tests all exist:
   - aggregator: by event_type (asc, desc), by entity_id (asc),
     verdict NULLS LAST, rejects unknown column, rejects unknown
     direction.
   - dashboard: header button for timestamp; 400 on bad sort; 400 on
     bad dir; chevron + aria-sort on active column; filter + sort +
     pagination interop.

4. **`message` column is asserted to NOT be a sort button** — somewhere
   a test confirms the `message` header remains plain text.

5. **CSS class assertions** — attribute-scoped form (I-00067).

6. **Targeted-run discipline** — `tests_passed` from targeted runs
   only.

### TDD RED Evidence

Coverage step — `tdd_red_evidence = "n/a — coverage step (tests-impl)"`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_auto_merge_aggregator.py tests/dashboard/test_auto_merge_routes.py -v
```

Missing named tests in collection list → CRITICAL.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "I-00095",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
