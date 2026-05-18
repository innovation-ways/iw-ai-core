# I-00096_S09_CodeReview_Final_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Review Step**: S09 (Final Review)
**Implementation Steps Reviewed**: S01..S08

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies. No new migrations.

## Input Files

- `uv run iw item-status I-00096 --json`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- `ai-dev/active/I-00096/I-00096_Functional.md`
- All reports in `ai-dev/active/I-00096/reports/`
- All files in S01/S03/S05/S07 `files_changed`

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S09_CodeReview_Final_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Completeness vs Design**: AC1..AC5 each map to existing code +
   tests.
2. **Cross-Agent Consistency**:
   - The flag name in `request.state.<...>` set by S01 matches the
     name read by the topbar template.
   - The `include_non_auto_merge` param name on the aggregator matches
     what S05 passes.
   - The `all` query param name matches what the toggle URL emits in
     S01.
   - The CSS class name `auto-merge-show-all-toggle` is consistent
     across template, CSS, and test assertions.
3. **Integration**:
   - Default GET `/auto-merge/events` excludes non-auto-merge.
   - `?all=1` includes them.
   - Filter chip URLs propagate `all=1` correctly.
   - Pagination Prev/Next propagate `all=1` correctly.
   - The auto-merge page renders exactly one chip; other pages render
     one (the topbar one).
4. **Architecture**: routers thin; SQL composed via SQLAlchemy
   `or_()`/`like()`, no raw strings; CSS appended plain to
   `styles.css`.
5. **Security**: no `| safe` filter; no user-controlled values
   interpolated into SQL.
6. **Functional doc accurate**.

## Test Verification (NON-NEGOTIABLE)

Targeted only — re-run the two files this item touches, no more.
Full-suite execution is owned by S14 (unit-tests QV gate) and S15
(integration-tests QV gate); duplicating here caused the I-00073
timeout pattern.

```bash
uv run pytest \
  tests/unit/test_auto_merge_aggregator.py \
  tests/dashboard/test_auto_merge_routes.py -v
```

Any failure in the targeted run → CRITICAL.
If S14 or S15 fail downstream, the workflow halts at the QV gate —
that is the intended owner of full-suite regressions.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-final-impl",
  "work_item": "I-00096",
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
