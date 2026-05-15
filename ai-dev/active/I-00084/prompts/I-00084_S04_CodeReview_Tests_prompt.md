# I-00084_S04_CodeReview_Tests_prompt

**Work Item**: I-00084 — Stale origin/main ref breaks make diff-coverage
**Step**: S04
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00084/I-00084_Issue_Design.md`
- `ai-dev/work/I-00084/reports/I-00084_S03_Tests_report.md`
- `tests/integration/test_setup_worktree_origin_main_sync.py`

## Output Files

- `ai-dev/work/I-00084/reports/I-00084_S04_CodeReview_report.md`

## Review Checklist

### CRITICAL

- **Reproduction test would fail pre-fix.** Read the test logic; if it
  would have passed against pre-S01 (no sync), it is not a regression
  test.
- **Semantic assertions only.** No `"origin" in remotes` shape checks.

### HIGH

- Both ACs covered (sync happens, idempotent).
- Test cleans up its `tmp_path` (pytest auto-cleanup is sufficient).
- No live DB / network usage.

### MEDIUM

- Test naming: `test_i00084_<scenario>`.
- Helper for fake-repo setup is small / readable.

## Verdict

`pass` or `needs-fix` with grouped findings.
