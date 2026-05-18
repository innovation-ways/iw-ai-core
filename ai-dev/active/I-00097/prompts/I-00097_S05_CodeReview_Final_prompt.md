# I-00097_S05_CodeReview_Final_prompt

**Work Item**: I-00097 — Auto-merge polish — token cost formatting & entity_id linkification
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies. No new migrations.

## Input Files

- `uv run iw item-status I-00097 --json`
- `ai-dev/active/I-00097/I-00097_Issue_Design.md`
- `ai-dev/active/I-00097/I-00097_Functional.md`
- All reports
- All files in S01/S03 `files_changed`

## Output Files

- `ai-dev/active/I-00097/reports/I-00097_S05_CodeReview_Final_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Completeness vs Design**: AC1..AC6 map to existing code + tests.
2. **Cross-Agent Consistency**:
   - The URL pattern in S01's `<a href="/project/.../item/<id>">`
     (singular `item`) matches what S03's regex tests expect and
     matches the actual route in `dashboard/routers/items.py:1124`.
   - The link colour class (`text-primary`) matches the rest of the
     dashboard's link styling.
3. **Integration**: `/auto-merge` renders cleanly with the new
   formatting; clicking a linked entity_id navigates to the item
   detail page; rendering with non-IW entity_ids does NOT linkify.
4. **Architecture / Conventions**: template-only change, plain CSS if
   any, no new JS, no docker.
5. **Security**: no `| safe`; auto-escape preserved.
6. **Functional doc accurate**.

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
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00097",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "missing_requirements": [],
  "notes": ""
}
```
