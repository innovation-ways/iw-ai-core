# I-00084_S05_CodeReview_Final_prompt

**Work Item**: I-00084 — Stale origin/main ref breaks make diff-coverage
**Step**: S05
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/I-00084/I-00084_Issue_Design.md`
- All S01..S04 reports
- Full diff: `git diff origin/main...HEAD` and unstaged.

## Output Files

- `ai-dev/work/I-00084/reports/I-00084_S05_CodeReviewFinal_report.md`

## Cross-Agent Final Review

### Independently re-verify

- Reproduction + idempotency tests pass locally.
- `git diff --stat` shows ONLY: `executor/setup_worktree.sh`, `Makefile`,
  `tests/integration/test_setup_worktree_origin_main_sync.py`. ANY other
  file is CRITICAL.

### Confirm

- Both insertion sites (setup_worktree.sh + Makefile) include the sync.
- Both invocations are idempotent.
- No `origin` (real-remote) fetch was added by mistake — must be
  `git fetch . main:...` (local-only).
- Inline comment cites I-00084 in both insertion sites.

### Bonus check

- Run `make diff-coverage` from this very worktree and verify the diff
  list shows only this CR's three files. If it shows extras, the fix
  doesn't actually work in production (which would be embarrassing for
  this CR specifically).

## Verdict

`pass` or `needs-fix`.
