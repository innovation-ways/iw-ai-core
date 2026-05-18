# I-00092_S05_CodeReview_Final_prompt

**Work Item**: I-00092 — Auto-merge filter chip never highlights the active filter
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies. No new migration files allowed; no docker commands.

## Input Files

- `uv run iw item-status I-00092 --json`
- `ai-dev/active/I-00092/I-00092_Issue_Design.md`
- `ai-dev/active/I-00092/I-00092_Functional.md`
- All step reports in `ai-dev/active/I-00092/reports/`
- All files in any S01/S03 `files_changed`

## Output Files

- `ai-dev/active/I-00092/reports/I-00092_S05_CodeReview_Final_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Completeness vs Design**: AC1..AC4 each map to existing code +
   tests.
2. **Cross-Agent Consistency**: the class names the template emits
   (`bg-primary`, `border-primary`, `text-primary-foreground`) match
   what S03's tests look for via attribute-scoped regex.
3. **Integration**: rendering `/auto-merge/events?type=merge_auto_resolved`
   highlights exactly one chip; rendering with no `type` highlights
   `all`. Verify by manual `curl` if needed.
4. **Tests Holistic**: no shape-only assertions, no test placed under
   `tests/unit/` or `tests/integration/` that uses `client`.
5. **Architecture / Conventions**: no docker commands, no migrations,
   plain CSS only if needed, Jinja2 `format` calls remain `%`-style.
6. **Security**: no `| safe` filter added to user-controlled values; the
   `title` attribute uses Jinja2 auto-escape.

## Test Verification (NON-NEGOTIABLE)

Final review owns the full suite:

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
  "work_item": "I-00092",
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
