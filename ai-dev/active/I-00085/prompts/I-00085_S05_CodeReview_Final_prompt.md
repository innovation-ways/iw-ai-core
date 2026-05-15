# I-00085_S05_CodeReview_Final_prompt

**Work Item**: I-00085 — .mypy_cache triggers gitleaks false positives
**Step**: S05
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/I-00085/I-00085_Issue_Design.md`
- All S01..S04 reports
- Full diff: `git diff origin/main...HEAD` and unstaged.

## Output Files

- `ai-dev/work/I-00085/reports/I-00085_S05_CodeReviewFinal_report.md`

## Cross-Agent Final Review

### Independently re-verify

- Reproduction + negative tests both pass locally.
- `git diff --stat` shows ONLY: `.gitleaks.toml`,
  `tests/integration/test_security_secrets_cache_independence.py`. ANY
  other file is CRITICAL.

### Confirm

- Three allowlist entries added (`.mypy_cache/`, `.ruff_cache/`,
  `.pytest_cache/`).
- Inline comment cites I-00085.
- Allowlist entries match existing style (`(?i)(?:^|/)`).
- The negative test still catches real secrets (run it locally; sanity
  check).
- `make security-secrets` runs clean from a worktree where
  `make type-check` was just executed.

## Verdict

`pass` or `needs-fix`.
