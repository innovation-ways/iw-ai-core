# I-00085_S04_CodeReview_Tests_prompt

**Work Item**: I-00085 — .mypy_cache triggers gitleaks false positives
**Step**: S04
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00085/I-00085_Issue_Design.md`
- `ai-dev/work/I-00085/reports/I-00085_S03_Tests_report.md`
- `tests/integration/test_security_secrets_cache_independence.py`

## Output Files

- `ai-dev/work/I-00085/reports/I-00085_S04_CodeReview_report.md`

## Review Checklist

### CRITICAL

- **Negative test exists and is real**: AC3 requires a test that
  confirms real secrets are still detected. If the test file only
  contains the reproduction case (positive path), flag CRITICAL.
- **No real secrets committed**: the negative-path fixture must use
  a documented test pattern (e.g., `AKIAIOSFODNN7EXAMPLE`), never a
  real-shaped key.
- **Fixture cleanup is bulletproof**: try/finally or pytest fixture
  teardown — never a bare `git rm` call inside the test body that won't
  run on failure.

### HIGH

- Reproduction test would FAIL pre-S01 (no `.mypy_cache/` allowance).
- Both ACs covered (positive + negative).
- No live DB usage.

### MEDIUM

- Test naming `test_i00085_<scenario>`.
- Marker / xdist-safety: documented if relevant.

## Verdict

`pass` or `needs-fix` with grouped findings.
