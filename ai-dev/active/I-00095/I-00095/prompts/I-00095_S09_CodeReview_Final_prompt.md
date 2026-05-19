# I-00095_S09_CodeReview_Final_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Review Step**: S09 (Final Review)
**Implementation Steps Reviewed**: S01..S08

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies. No new migrations; no docker.

## Input Files

- `uv run iw item-status I-00095 --json`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/I-00095_Functional.md`
- All step reports in `ai-dev/active/I-00095/reports/`
- All files in S01/S03/S05/S07 `files_changed`

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S09_CodeReview_Final_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Completeness vs Design**: AC1..AC6 each map to existing code +
   tests.

2. **Cross-Agent Consistency — the whitelist matches across layers**:
   - S01's `SORTABLE_COLUMNS` keys ∈
     `{"created_at","event_type","entity_id","verdict"}`.
   - S03's `SORT_VALUES` tuple ∈ the same set.
   - S05's template `columns` list marks exactly the same four as
     `sortable=True`.
   - S07's tests assert against the same set.

   Any drift across layers → CRITICAL.

3. **Integration**: a real `GET /auto-merge/events?sort=event_type&dir=asc`
   returns 200 and the table is correctly ordered (verify via `curl`
   if you can).

4. **Filter + sort + pagination compose**: AC5 holds.

5. **SQL injection safety**: there is NO place where a user-supplied
   string is interpolated into a SQL fragment — all sorting goes
   through SQLAlchemy `ColumnElement` objects. Verify.

6. **Architecture / Conventions**: routers stay thin (validate +
   delegate); business logic in aggregator; templates render from
   context only.

7. **Functional doc accurate**: matches the actual behaviour shipped.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make allure-integration
```

Integration failure → CRITICAL.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-final-impl",
  "work_item": "I-00095",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "missing_requirements": [],
  "notes": ""
}
```
