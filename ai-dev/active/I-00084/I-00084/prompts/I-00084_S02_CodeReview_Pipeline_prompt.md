# I-00084_S02_CodeReview_Pipeline_prompt

**Work Item**: I-00084 — Stale origin/main ref breaks make diff-coverage
**Step**: S02
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00084/I-00084_Issue_Design.md`
- `ai-dev/work/I-00084/reports/I-00084_S01_Pipeline_report.md`
- The S01 diff (`executor/worktree_setup.sh`, `Makefile`)

## Output Files

- `ai-dev/work/I-00084/reports/I-00084_S02_CodeReview_report.md`

## Review Checklist

### CRITICAL

- **GitHub-flow regression**: any change that affects fetching from a
  real `origin` remote (the fix must use `git fetch . main:...`, fetching
  from `.` — the local repo).
- **Non-idempotent**: the second run must be a no-op. If the fix runs
  some destructive `git update-ref` or otherwise mutates state on every
  call, flag it.

### HIGH

- Both insertion sites done: `worktree_setup.sh` AND `Makefile`.
- Inline comment cites I-00084 so future maintainers understand why.
- Error handling: `2>/dev/null || true` (or equivalent) protects against
  edge cases where local `main` does not exist.
- Shell quoting matches existing style in `executor/worktree_setup.sh`.

### MEDIUM

- TDD RED evidence captured.
- The reproduction test is referenced in the report.

### LOW

- Optional log line on sync (operator visibility) — nice-to-have.

## Verdict

`pass` or `needs-fix` with grouped findings.
