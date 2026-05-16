# I-00083_S04_CodeReview_Tests_prompt

**Work Item**: I-00083 — Branch-base drift across in-flight items
**Step**: S04
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00083/I-00083_Issue_Design.md`
- `ai-dev/work/I-00083/reports/I-00083_S03_Tests_report.md`
- `tests/integration/test_branch_base_drift.py`

## Output Files

- `ai-dev/work/I-00083/reports/I-00083_S04_CodeReview_report.md`

## Review Checklist

### CRITICAL

- **Reproduction test would fail pre-fix.** Read the test logic; if it
  would also pass against the broken pre-S01 chore-commit behaviour,
  it is not actually a regression test.
- **Semantic assertions only.** No `len(...) > 0` / `"key" in dict`.

### HIGH

- All 3 ACs covered: AC1 (no inheritance), AC2 (test exists), AC3
  (happy path preserved).
- No live DB usage (port 5433); only testcontainer or `tmp_path`.
- Two-item simulation actually exercises the in-flight overlap (not
  just two items run sequentially with no overlap window).

### MEDIUM

- Test naming `test_i00083_<scenario>`.
- Helper for fake-repo setup is reusable / documented.

## Verdict

`pass` or `needs-fix` with grouped findings.
