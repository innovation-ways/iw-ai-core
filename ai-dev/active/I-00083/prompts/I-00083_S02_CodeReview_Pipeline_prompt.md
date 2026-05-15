# I-00083_S02_CodeReview_Pipeline_prompt

**Work Item**: I-00083 — Branch-base drift across in-flight items
**Step**: S02
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00083/I-00083_Issue_Design.md`
- `ai-dev/work/I-00083/reports/I-00083_S01_Pipeline_report.md`
- The S01 diff

## Output Files

- `ai-dev/work/I-00083/reports/I-00083_S02_CodeReview_report.md`

## Review Checklist

### CRITICAL

- **Backwards compatibility broken**: any change that retroactively
  rewrites already-shipped chore commits or breaks ongoing in-flight
  items.
- **Single-item happy path regressed**: solo-item runs must behave
  exactly as today.
- **Merge-path behaviour changed**: this fix is approval-time / create-time
  only; merges must be untouched.

### HIGH

- Option chosen + justified in S01 report.
- Excluded path list explicit and commented in code (not implicit /
  derived).
- Daemon log line shape matches the spec.
- Existing git-helper wrappers used; no ad-hoc `subprocess.run(["git", ...])`.

### MEDIUM

- TDD RED evidence captured.
- New behaviour covered by both reproduction test and happy-path
  regression test in S03 (verify in S04, but flag here if S03 plan
  looks weak from the S01 report).

## Verdict

`pass` or `needs-fix` with grouped findings.

## Subagent Result Contract

Standard `code-review-impl` JSON.
