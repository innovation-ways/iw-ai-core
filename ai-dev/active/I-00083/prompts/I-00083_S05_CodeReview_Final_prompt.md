# I-00083_S05_CodeReview_Final_prompt

**Work Item**: I-00083 — Branch-base drift across in-flight items
**Step**: S05
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/I-00083/I-00083_Issue_Design.md`
- All S01..S04 reports
- Full diff: `git diff origin/main...HEAD` and unstaged.

## Output Files

- `ai-dev/work/I-00083/reports/I-00083_S05_CodeReviewFinal_report.md`

## Cross-Agent Final Review

### Independently re-verify

- Reproduction test passes locally.
- Happy-path regression passes locally.
- `git diff --stat` shows ONLY files in `scope.allowed_paths`. ANY other
  file is CRITICAL.

### Confirm

- Option chosen at S01 is justified, documented, and consistent across
  the diff.
- The chore-commit exclusion list is comprehensive (design docs +
  manifest + prompts only).
- Daemon log line matches the spec.
- Backwards compatibility: items approved before this change still work.
- Merge-path behaviour is untouched.

## Verdict

`pass` or `needs-fix`.
