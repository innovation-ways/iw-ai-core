# I-00085 S02 Code Review Report

**Work Item**: I-00085 — .mypy_cache triggers gitleaks false positives
**Step**: S02
**Agent**: code-review-impl
**Date**: 2026-05-15
**Verdict**: PASS

---

## Summary

S01's changes to `.gitleaks.toml` are minimal, correct, and safe. All CRITICAL, HIGH, and MEDIUM checklist items pass. No findings.

---

## Checklist Results

### CRITICAL

| # | Check | Result |
|---|-------|--------|
| C1 | **Over-broad allowlist** — entries must be specific cache-dir globs, not catch-alls | PASS |
| C2 | **Correct Go regexp syntax** — config loads without startup errors | PASS |

**C1 detail**: The three additions are:
```toml
'''(?i)(?:^|/)\.mypy_cache/''',
'''(?i)(?:^|/)\.ruff_cache/''',
'''(?i)(?:^|/)\.pytest_cache/''',
```
Each escapes the leading `.` (`\.`) so it only matches the exact tool-managed directory names. No catch-alls (`\.cache/`, `**/cache/**`, etc.) are present.

**C2 detail**: `gitleaks detect --config .gitleaks.toml --no-git --source .` completed with exit 0 and "no leaks found" — no parse or compile errors on startup.

### HIGH

| # | Check | Result |
|---|-------|--------|
| H1 | Three entries added: `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/` | PASS |
| H2 | Style matches existing `__pycache__/` entry (`(?i)(?:^|/)` prefix, `'''` quoting) | PASS |
| H3 | Inline comment cites I-00085 | PASS |
| H4 | `make security-secrets` returns 0 leaks after `make type-check` populates cache | PASS |

**H3 detail**: Comment reads:
```
# I-00085: tool-managed cache directories — same rationale as __pycache__/
# above. .mypy_cache/ in particular contains vendored type-stub strings
# (e.g., *.local) that match the iw-internal-fqdn rule.
```
Comment is directly above the three new entries, inserted immediately after the existing `__pycache__/` entry — exactly where a reader would expect it.

**H4 detail**: S01 report confirmed `make type-check && make security-secrets` exits 0. Direct gitleaks run during this review also returned `no leaks found`.

### MEDIUM

| # | Check | Result |
|---|-------|--------|
| M1 | TDD RED evidence captured | PASS |

**M1 detail**: S01 report documents the pre-fix RED state:
> Running gitleaks against synthetic `.mypy_cache/3.12/threading.data.json` containing `{"fullname": "threading.local"}` produced `leaks found: 1, Return code: 1`. The `iw-internal-fqdn` rule matched `threading.local`.

---

## Test Verification

Both integration tests pass:

```
tests/integration/test_security_secrets_cache_independence.py::test_i00085_mypy_cache_does_not_trigger_false_positives PASSED
tests/integration/test_security_secrets_cache_independence.py::test_i00085_real_secret_still_detected PASSED
2 passed in 0.69s
```

The control test (`test_i00085_real_secret_still_detected`) confirms that real secrets (`AKIA1234567890ABCDEF` at `leak_target/config.py`) are still detected — the allowlist entries do not mask secrets at non-cache paths.

---

## Files Reviewed

| File | Change | Assessment |
|------|--------|------------|
| `.gitleaks.toml` | +6 lines (comment + 3 allowlist entries) | Correct, specific, well-placed |
| `tests/integration/test_security_secrets_cache_independence.py` | New file (87 lines) | Correct skip guards, strong assertions, proper sandbox isolation |

---

## Findings

None. No CRITICAL, HIGH, MEDIUM, or LOW findings.

---

## Verdict

**PASS** — S01 implementation is correct and safe. Ready to proceed to S03 (Tests).
