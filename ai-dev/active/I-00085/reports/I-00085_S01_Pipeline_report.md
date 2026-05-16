# I-00085 S01 Pipeline Report

**Work Item**: I-00085
**Step**: S01
**Agent**: pipeline-impl
**Date**: 2026-05-15

## Summary

Added `.mypy_cache/`, `.ruff_cache/`, and `.pytest_cache/` to the `.gitleaks.toml`
`[allowlist].paths` block and created a regression test that exercises the fix.

## TDD RED Evidence

Before the fix, running gitleaks against a synthetic `.mypy_cache/3.12/threading.data.json`
containing `{"fullname": "threading.local"}` produced:

```
leaks found: 1
Return code: 1
```

The `iw-internal-fqdn` rule (`[a-zA-Z0-9][a-zA-Z0-9-]{0,62}\.(?:internal|corp|local|lan|intranet)\b`)
matched `threading.local` in the cached type-stub file.

## Files Changed

### `.gitleaks.toml`

Added three allowlist path entries immediately after the existing `__pycache__/` entry:

```toml
  # I-00085: tool-managed cache directories — same rationale as __pycache__/
  # above. .mypy_cache/ in particular contains vendored type-stub strings
  # (e.g., *.local) that match the iw-internal-fqdn rule.
  '''(?i)(?:^|/)\.mypy_cache/''',
  '''(?i)(?:^|/)\.ruff_cache/''',
  '''(?i)(?:^|/)\.pytest_cache/''',
```

### `tests/integration/test_security_secrets_cache_independence.py`

New test file with two tests:

1. `test_i00085_mypy_cache_does_not_trigger_false_positives` — places a synthetic
   `.mypy_cache/3.12/threading.data.json` with `{"fullname": "threading.local"}` in
   a `tmp_path` sandbox and verifies gitleaks exits 0 after the fix (FAILS pre-fix,
   PASSES post-fix).

2. `test_i00085_real_secret_still_detected` — control test that places an AWS-shaped
   key `AKIA1234567890ABCDEF` at `leak_target/config.py` (non-allowlisted path) and
   verifies gitleaks still exits non-zero. Passes pre- and post-fix, guarding against
   over-broad allowlist edits.

Both tests skip cleanly when `gitleaks` is not on PATH.

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | OK — 708 files already formatted |
| `make type-check` | OK — no issues in 249 source files |
| `make lint` | OK — all checks passed |

## Fix Verification

```
make type-check && make security-secrets
→ mypy: Success: no issues found in 249 source files
→ gitleaks: no leaks found
→ [security-secrets] OK
```

Running `make type-check` first populates `.mypy_cache/` (the exact scenario that
produced the CR-00053 false positives), and `make security-secrets` exits 0.

## Test Results

```
tests/integration/test_security_secrets_cache_independence.py::test_i00085_mypy_cache_does_not_trigger_false_positives PASSED
tests/integration/test_security_secrets_cache_independence.py::test_i00085_real_secret_still_detected PASSED
2 passed in 0.69s
```

## Decisions

- The second test assertion was corrected: gitleaks emits its summary to stderr, not
  stdout. The assertion now checks `result.stdout + result.stderr` (combined) for
  either the key string or "leaks found".
- Tests are run with `--no-cov` when invoked in isolation to avoid the `fail_under=50`
  coverage threshold firing on a 2-test run.

## Issues

None. The fix is minimal (3 TOML lines + comment), the test exercises the exact
failure mode from CR-00053 S16, and all quality gates pass.
