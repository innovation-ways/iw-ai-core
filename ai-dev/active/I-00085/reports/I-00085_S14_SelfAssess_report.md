# I-00085 S14 Self-Assessment Report

**Work Item**: I-00085 — `.mypy_cache/` triggers gitleaks false positives
**Step**: S14
**Agent**: self-assess-impl
**Date**: 2026-05-16

---

## Summary

I-00085 is a minimal, clean incident resolution. The fix (3 allowlist entries + comment in
`.gitleaks.toml`) landed correctly in S01, passed all code reviews (S02, S04, S05) without
findings, and cleared all 8 QV gates (S06–S13) on first try with zero fix cycles.

---

## Focus Area 1: Did S13 (security-secrets) run clean on first try?

**YES — confirmed clean on first try, no operator intervention.**

S13 report:
```
Exit code: 0  |  Result: PASS  |  Duration: 1s
gitleaks: scanned ~5154378 bytes (5.15 MB) in 198ms — no leaks found
[security-secrets] OK
```

This directly validates the fix: `.mypy_cache/` files containing vendored type-stub
strings (e.g., `threading.local`) no longer trigger the `iw-internal-fqdn` rule.
Pre-fix, this gate required `rm -rf .mypy_cache` as an operator workaround (per
CR-00053 S16 experience). Post-fix, no workaround is needed.

---

## Focus Area 2: Did `make type-check` (S09) populate `.mypy_cache/` before S13?

**YES — S09 ran successfully before S13 in the canonical gate order.**

Gate sequence: S09 (typecheck) → S10 (unit-tests) → S11 (integration-tests) →
S12 (diff-coverage) → S13 (security-secrets).

S09 report: `uv run mypy orch/ dashboard/` → "Success: no issues found in 249 source
files" (exit 0). This run populates `.mypy_cache/` with cached type stubs. S13 then
ran against a worktree that had `.mypy_cache/` populated and reported zero leaks —
confirming the allowlist works in the exact scenario the bug was triggered in.

S01's fix verification also explicitly tested `make type-check && make security-secrets`
sequentially and confirmed both exit 0 after the fix.

---

## Focus Area 3: Cross-CR pattern vs CR-00053's S16 false positives

CR-00053's S16 found 3 false positives:
- `.mypy_cache/3.12/sqlalchemy/event/attr.data.json`
- `.mypy_cache/3.12/sqlalchemy/event/base.data.json`
- `.mypy_cache/3.12/threading.data.json`

All matched the `iw-internal-fqdn` rule (`[a-zA-Z0-9][a-zA-Z0-9-]{0,62}\.(?:internal|corp|local|lan|intranet)\b`)
on cached vendored Python type stub strings (e.g., `"threading.local"`, `"*.local"`).

This CR's fix adds:
```toml
# I-00085: tool-managed cache directories — same rationale as __pycache__/
# above. .mypy_cache/ in particular contains vendored type-stub strings
# (e.g., *.local) that match the iw-internal-fqdn rule.
'''(?i)(?:^|/)\.mypy_cache/''',
'''(?i)(?:^|/)\.ruff_cache/''',
'''(?i)(?:^|/)\.pytest_cache/''',
```

The pattern is identical in structure to the existing `__pycache__/` allowlist entry —
same rationale, same regex style, same TOML quoting. S05 (final cross-agent review)
explicitly verified all three entries matched this style.

The control test (`test_i00085_real_secret_still_detected`) confirmed the allowlist is
not over-broad: an AWS-shaped key `AKIA1234567890ABCDEF` at a non-allowlisted path
(`leak_target/config.py`) is still detected by gitleaks.

---

## QV Gate Summary (S06–S13)

| Step | Gate              | Result | Fix Cycles |
|------|-------------------|--------|------------|
| S06  | lint              | PASS   | 0          |
| S07  | assertions        | PASS   | 0          |
| S08  | format            | PASS   | 0          |
| S09  | type-check        | PASS   | 0          |
| S10  | unit-tests        | PASS   | 0          |
| S11  | integration-tests | PASS   | 0          |
| S12  | diff-coverage     | PASS   | 0          |
| S13  | security-secrets  | PASS   | 0          |

All 8 gates passed on first try. Zero fix cycles.

---

## Files Changed

| File | Change |
|------|--------|
| `.gitleaks.toml` | +6 lines: comment + 3 allowlist entries (`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`) |
| `tests/integration/test_security_secrets_cache_independence.py` | New file, 87 lines — 2 integration tests |

---

## Test Results

- `test_i00085_mypy_cache_does_not_trigger_false_positives`: PASS (RED pre-fix, GREEN post-fix — TDD confirmed)
- `test_i00085_real_secret_still_detected`: PASS (control test, passes pre- and post-fix)
- Regression check: 2422 passed, 33 skipped (S12 full suite), 2937 passed (S10 unit suite) — no regressions
- Diff coverage: 90% at 90% threshold — PASS

---

## Acceptance Criteria Verification

| AC | Criterion | Status |
|----|-----------|--------|
| AC1 | `make type-check && make security-secrets` exits 0 | PASS (verified in S01, confirmed by S09→S13 gate ordering) |
| AC2 | `test_security_secrets_cache_independence.py` passes | PASS (S10, S11, S12) |
| AC3 | Real secret `AKIA1234567890ABCDEF` still detected at non-allowlisted path | PASS (control test confirmed) |

---

## Code Review Summary

| Step | Reviewer | Verdict | Findings |
|------|----------|---------|----------|
| S02  | code-review-impl (Pipeline) | PASS | None |
| S04  | code-review-impl (Tests)    | PASS | None — one minor deviation noted (subprocess vs shutil.which for gitleaks availability check), no correctness impact |
| S05  | code-review-final-impl      | PASS | None — all 10 cross-agent checklist items confirmed |

---

## Observations

1. **Scope discipline**: The fix is exactly as small as the design specified — 3 TOML
   lines + comment + 87-line test file. No scope creep.

2. **S09 duration = 0s**: Displayed as 0 seconds in the gate report (rounding). Mypy
   did run (`249 source files` confirmed) so `.mypy_cache/` was populated before S13.

3. **Sibling incidents**: I-00085 is the smallest of the I-00082..I-00085 sibling
   incidents. Unlike I-00082 (runtime override API), I-00083, and I-00084, this fix
   required no schema changes, no migration, and no daemon changes — purely config.

4. **No fix cycles required**: The zero-fix-cycle run confirms that the design was
   precise and S01's implementation was correct on the first attempt.

---

## Verdict

**PASS** — I-00085 is complete. The root cause (missing `.mypy_cache/` allowlist entry
in `.gitleaks.toml`) is fixed, the fix is verified by S13 passing on first try with
`.mypy_cache/` populated, and regression tests guard against recurrence. The CR-00053
S16 false-positive pattern will not recur in future worktrees.
