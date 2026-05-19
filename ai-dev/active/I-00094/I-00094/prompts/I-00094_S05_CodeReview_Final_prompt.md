# I-00094_S05_CodeReview_Final_prompt

**Work Item**: I-00094 — Auto-merge htmx-only `<a>` tags render with text cursor and bad accessibility
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies. No new migrations; no docker.

## Input Files

- `uv run iw item-status I-00094 --json`
- `ai-dev/active/I-00094/I-00094_Issue_Design.md`
- `ai-dev/active/I-00094/I-00094_Functional.md`
- All step reports in `ai-dev/active/I-00094/reports/`
- All files in S01/S03 `files_changed`

## Output Files

- `ai-dev/active/I-00094/reports/I-00094_S05_CodeReview_Final_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Completeness vs Design**: AC1..AC6 map to existing code + tests.
2. **Cross-Agent Consistency**: every test's regex matches what S01
   actually emits; e.g., if S03 expects `<button type="button" …`,
   S01 MUST include `type="button"` not just `<button …>`.
3. **Integration**: nothing else in the dashboard breaks. Run
   `grep -rn '<a\b[^>]*\bhx-get=' dashboard/templates/fragments/`
   and verify auto-merge fragments are clean.
4. **No regressions on click behaviour**: `<button hx-get>` works the
   same as `<a hx-get>` in htmx — confirmed by S11 integration tests.
5. **Architecture / Conventions**: no docker, no migrations, plain
   CSS, Jinja2 `format` calls `%`-style.
6. **Security**: no new `| safe` filter usage; `<button>` body still
   auto-escapes.
7. **Functional doc accurate**: matches what users now experience.

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
  "work_item": "I-00094",
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
