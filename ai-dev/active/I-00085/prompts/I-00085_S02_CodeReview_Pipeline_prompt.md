# I-00085_S02_CodeReview_Pipeline_prompt

**Work Item**: I-00085 — .mypy_cache triggers gitleaks false positives
**Step**: S02
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00085/I-00085_Issue_Design.md`
- `ai-dev/work/I-00085/reports/I-00085_S01_Pipeline_report.md`
- The S01 diff (`.gitleaks.toml`)

## Output Files

- `ai-dev/work/I-00085/reports/I-00085_S02_CodeReview_report.md`

## Review Checklist

### CRITICAL

- **Over-broad allowlist**: any allowlist entry that would mask real
  secrets. The three additions must be specific cache-directory globs
  (e.g., `(?:^|/)\.mypy_cache/`), not catch-alls (e.g., `\.cache/`,
  `**/cache/**`).
- **Wrong regex syntax**: gitleaks uses Go regexp; the three entries
  must compile cleanly. Verify by running `gitleaks detect --config
  .gitleaks.toml --no-git` and confirming no startup errors.

### HIGH

- Three entries added: `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`.
- Style matches existing `__pycache__/` entry (same `(?i)(?:^|/)` prefix).
- Inline comment cites I-00085.
- `make security-secrets` (verified manually post-edit) returns 0 leaks
  even after `make type-check` populates the cache.

### MEDIUM

- TDD RED evidence captured.

## Verdict

`pass` or `needs-fix` with grouped findings.
