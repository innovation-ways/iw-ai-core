# I-00085 S03 Tests Report

**Work Item**: I-00085
**Step**: S03
**Agent**: tests-impl
**Date**: 2026-05-15

## Summary

Verified and confirmed the two integration tests in
`tests/integration/test_security_secrets_cache_independence.py`.
The file was already created in S01 (pipeline agent). This step
reviewed the tests for correctness, captured TDD RED evidence
against the pre-fix config, and confirmed both tests pass GREEN
with the post-fix config.

## TDD RED Evidence

Running the first test's payload (`{"fullname": "threading.local"}` in
`.mypy_cache/3.12/threading.data.json`) against the pre-fix
`.gitleaks.toml` (HEAD~1) confirms the bug is real:

```
gitleaks detect --no-git --source <tmp> --config /tmp/pre_fix.toml
leaks found: 1
Exit code: 1
```

The `iw-internal-fqdn` rule (`[a-zA-Z0-9][a-zA-Z0-9-]{0,62}\.(?:internal|corp|local|lan|intranet)\b`)
matched `threading.local` in the cached type-stub content. This
reproduces exactly what CR-00053 S16 encountered.

## Files

### `tests/integration/test_security_secrets_cache_independence.py`

This file was created in S01 and contains the two required tests:

1. `test_i00085_mypy_cache_does_not_trigger_false_positives` — places
   `{"fullname": "threading.local"}` at `.mypy_cache/3.12/threading.data.json`
   in a `tmp_path` sandbox and asserts `result.returncode == 0` post-fix.
   Fails against pre-fix config (RED), passes against post-fix config (GREEN).

2. `test_i00085_real_secret_still_detected` — places `AKIA1234567890ABCDEF`
   at `leak_target/config.py` (non-allowlisted path) and asserts
   `result.returncode != 0`. Guards against over-broad allowlist edits.
   Passes both pre- and post-fix.

Both tests:
- Use `@pytest.mark.skipif(not _gitleaks_available(), ...)` to skip when
  gitleaks is not on PATH.
- Use `--report-path` to write JSON output to `source / "_report.json"`
  (inside tmp_path, cleaned up by pytest automatically).
- Do not touch the worktree's `.mypy_cache/` or run `make type-check`.

## Test Results (Post-Fix GREEN)

```
tests/integration/test_security_secrets_cache_independence.py::test_i00085_mypy_cache_does_not_trigger_false_positives PASSED
tests/integration/test_security_secrets_cache_independence.py::test_i00085_real_secret_still_detected PASSED
2 passed in 0.70s
```

## Regression Check

Unit test suite run (2937 tests) shows no regressions:

```
2937 passed, 4 skipped, 5 xfailed, 2 xpassed, 46 warnings in 43.27s
```

## Observations

- The test file was already created by S01 (pipeline agent). S02 reviewed
  and approved it. S03 confirmed correctness, captured RED evidence, and
  verified GREEN.
- The `shutil.which` guard was implemented via `_gitleaks_available()` helper
  using `subprocess.run(["gitleaks", "version"])` — functionally equivalent
  to the `shutil.which` approach specified in the prompt.
- The control test's combined assertion (`result.stdout + result.stderr`)
  is correct: gitleaks writes summary text ("leaks found") to stderr and
  the JSON report to the `--report-path` file, not stdout. The assertion
  checks both channels to be robust.

## Decisions

- No changes were made to the test file — it already correctly implements
  both required tests per the design doc's "Test to Reproduce" section.
- TDD RED evidence was captured by running gitleaks directly against the
  pre-fix TOML (checked out from HEAD~1) rather than by reverting the fix.
