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

- Reproduction + control tests both pass locally with `uv run pytest
  tests/integration/test_security_secrets_cache_independence.py -v`.
- Run the control test in isolation and confirm it actually invokes
  gitleaks (`-v` plus a deliberately broken bad-secret string makes it
  fail — sanity-check the wiring, then revert).
- `git diff --stat` shows ONLY: `.gitleaks.toml`,
  `tests/integration/test_security_secrets_cache_independence.py`. ANY
  other file is CRITICAL.

### Confirm

- Three allowlist entries added (`.mypy_cache/`, `.ruff_cache/`,
  `.pytest_cache/`); no other allowlist edits.
- Inline comment cites I-00085.
- Allowlist entries match existing style (`(?i)(?:^|/)`).
- The control test's bad-secret string is NOT `AKIAIOSFODNN7EXAMPLE`
  (would be suppressed by `[allowlist].regexes`) and its path inside
  `tmp_path` does NOT fall under any `[allowlist].paths` regex.
- The tests do NOT shell out to `make security-secrets` or `make
  type-check` and do NOT mutate the worktree's `.mypy_cache/`. They
  run gitleaks against `tmp_path` only.
- `make security-secrets` runs clean against the real worktree after
  `make type-check` has populated `.mypy_cache/` (manual operator check).

## Verdict

`pass` or `needs-fix`.
