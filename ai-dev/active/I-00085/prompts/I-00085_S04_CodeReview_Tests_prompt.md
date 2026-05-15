# I-00085_S04_CodeReview_Tests_prompt

**Work Item**: I-00085 — .mypy_cache triggers gitleaks false positives
**Step**: S04
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00085/I-00085_Issue_Design.md`
- `ai-dev/work/I-00085/reports/I-00085_S03_Tests_report.md`
- `tests/integration/test_security_secrets_cache_independence.py`
- `.gitleaks.toml` — to verify the control test isn't sitting on top of
  an existing allowlist entry

## Output Files

- `ai-dev/work/I-00085/reports/I-00085_S04_CodeReview_report.md`

## Review Checklist

### CRITICAL

- **Negative/control test is real** — AC3 requires a test that confirms
  real secrets are still detected. If the test file only contains the
  reproduction case, flag CRITICAL.
- **Negative test does NOT trip allowlist** — verify by inspecting both:
  - The bad-secret string is NOT the `AKIAIOSFODNN7EXAMPLE` documented
    example. Anything containing the literal `AKIAIOSFODNN7EXAMPLE` is
    suppressed by `.gitleaks.toml` `[allowlist].regexes` (line ~120).
    The expected shape is `AKIA1234567890ABCDEF` or similar 16-char
    alphanumeric suffix that does not include `EXAMPLE`.
  - The bad-secret's path inside `tmp_path` does NOT fall under any
    `[allowlist].paths` regex (`tests/fixtures/`, `docs/`, `examples/`,
    `tests/unit/`, `tests/integration/`, `tests/dashboard/`, `ai-dev/`,
    `orch/oss/`, `dashboard/services/`, …). A fresh top-level directory
    like `leak_target/` inside `tmp_path` is correct.
  - If either check fails, the control test passes for the wrong reason
    (leak suppressed by allowlist, not by detection) — flag CRITICAL.
- **No real secrets committed** — the bad-secret string must be an
  obvious shape-matching fixture, never a real-shaped key from a
  credential store.
- **Sandbox isolation** — both tests must run gitleaks against
  `tmp_path` only, never against the real working tree. No
  `subprocess.run(["make", ...])` or `gitleaks detect --source .`.
  Don't mutate the worktree's `.mypy_cache/`.

### HIGH

- Reproduction test FAILS pre-S01 (synthetic `threading.local` payload
  in a `tmp_path/.mypy_cache/3.12/...` file → gitleaks must report a
  leak using the pre-fix config). The S03 report's `tdd_red_evidence`
  field should evidence this.
- Reproduction test runs gitleaks with `--config <project>/.gitleaks.toml`
  (the project config), not a stub.
- Both ACs covered (AC1+AC2 by reproduction test; AC3 by control test).
- `gitleaks`-missing guard uses `shutil.which("gitleaks")` →
  `pytest.skip(...)`, applied per-test (not at module load).
- No live DB usage; no Docker; xdist-safe (uses `tmp_path` only).

### MEDIUM

- Test naming `test_i00085_<scenario>`.
- Assertions are semantic (return code AND a string match for the
  control test), not bare substring checks.

## Verdict

`pass` or `needs-fix` with grouped findings.
