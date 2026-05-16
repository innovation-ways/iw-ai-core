# I-00085 S04 Code Review — Tests

**Work Item**: I-00085 — `.mypy_cache/` triggers gitleaks false positives
**Step**: S04
**Agent**: code-review-impl
**Date**: 2026-05-16
**Verdict**: PASS

---

## Files Reviewed

- `tests/integration/test_security_secrets_cache_independence.py`
- `.gitleaks.toml` (allowlist paths at lines 46-122; regexes at lines 125-133)
- `ai-dev/active/I-00085/reports/I-00085_S03_Tests_report.md`
- `ai-dev/active/I-00085/I-00085_Issue_Design.md`

---

## CRITICAL Checks — All Pass

### C1: Negative/control test is real
`test_i00085_real_secret_still_detected` (lines 65–86) is a genuine control test.
It places `AKIA1234567890ABCDEF` at `tmp_path / "leak_target" / "config.py"` and
asserts `result.returncode != 0`. The assertion would fail if the allowlist became
over-broad. **PASS.**

### C2: Control secret does NOT trip the documented-example allowlist
The planted string is `AKIA1234567890ABCDEF`. The `.gitleaks.toml` `regexes`
allowlist (line 126) suppresses only the literal `AKIAIOSFODNN7EXAMPLE`. The
control string contains no substring `EXAMPLE`, so it is not suppressed by that
regex, and not suppressed by any other regex in lines 126–133. **PASS.**

### C3: Control secret path is NOT under any allowlisted path
The file lands at `<tmp_path>/leak_target/config.py`. gitleaks is invoked with
`--source tmp_path`; it reports absolute paths. The top-level directory name
`leak_target` does not match any allowlist path pattern in `.gitleaks.toml`
lines 46–122 — not `docs/`, `tests/fixtures/`, `tests/unit/`, `tests/integration/`,
`tests/dashboard/`, `ai-dev/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`,
`__pycache__/`, `.git/`, `.venv/`, `venv/`, `node_modules/`, `dist/`, `build/`,
`logs/`, `allure-*`, `coverage/`, `htmlcov/`, `skills/iw-oss-publish/`, `orch/oss/`,
`dashboard/services/`, `.tmp/`, nor any per-file extension/name pattern.
Each test gets its own `tmp_path` (function-scoped), so there is no cross-test
contamination between the two tests. **PASS.**

### C4: No real secrets committed
`AKIA1234567890ABCDEF` is a synthetic, obviously sequential alphanumeric fixture
string — not from any credential store. **PASS.**

### C5: Sandbox isolation
Both tests call `_run_gitleaks(tmp_path)` which runs gitleaks with
`--source str(tmp_path)`. Neither test invokes any `make` target, neither calls
`subprocess.run(["make", ...])`, and neither reads or writes the worktree's
`.mypy_cache/`. The tests are xdist-safe (exclusive use of pytest's `tmp_path`
fixture). **PASS.**

---

## HIGH Checks — All Pass

### H1: Reproduction test FAILS pre-S01 (TDD RED evidence)
The S03 report's `TDD RED Evidence` section documents running the same payload
(`threading.local` in `.mypy_cache/3.12/threading.data.json`) against the pre-fix
TOML (HEAD~1) and observing `leaks found: 1`, exit code 1. The `iw-internal-fqdn`
rule matched `threading.local`. This reproduces the CR-00053 S16 finding exactly.
**PASS.**

### H2: Uses project `.gitleaks.toml` (not a stub)
`_run_gitleaks` passes `--config str(GITLEAKS_CONFIG)` where `GITLEAKS_CONFIG =
PROJECT_ROOT / ".gitleaks.toml"` (resolved from `Path(__file__).resolve().parents[2]`).
Tests exercise the actual project config. **PASS.**

### H3: Both ACs covered
- AC1 + AC2: `test_i00085_mypy_cache_does_not_trigger_false_positives` — places the
  CR-00053 S16 exact payload in `.mypy_cache/3.12/threading.data.json`, asserts
  `returncode == 0` post-fix. Fails pre-fix (RED), passes post-fix (GREEN). **PASS.**
- AC3: `test_i00085_real_secret_still_detected` — control test at non-allowlisted
  path. Guards against over-broad allowlist edits. Passes pre- and post-fix. **PASS.**

### H4: gitleaks-missing guard
Both tests use `@pytest.mark.skipif(not _gitleaks_available(), reason="gitleaks
binary not found on PATH")`. The `_gitleaks_available()` helper uses
`subprocess.run(["gitleaks", "version"])` and catches `FileNotFoundError` and
`CalledProcessError`, returning `False` when the binary is absent. The decorator
is applied per-test function (not a single module-level `pytest.skip()`), so each
test independently handles the absent-binary case.

Minor deviation: the checklist specified `shutil.which("gitleaks")`; the
implementation uses `subprocess.run`. Both detect the absent-binary condition.
The S03 report explicitly acknowledged this as "functionally equivalent." No
correctness impact. **PASS** (acknowledged deviation).

### H5: No live DB, no Docker, xdist-safe
No database imports, no `docker` or `docker compose` invocations, no shared
mutable state beyond `tmp_path`. **PASS.**

---

## MEDIUM Checks — All Pass

### M1: Test naming convention
- `test_i00085_mypy_cache_does_not_trigger_false_positives` ✓
- `test_i00085_real_secret_still_detected` ✓

Both follow `test_i00085_<scenario>`. **PASS.**

### M2: Semantic assertions
- Reproduction test: `result.returncode == 0` with a diagnostic message embedding
  both stdout and stderr on failure. **PASS.**
- Control test: `result.returncode != 0` AND `"AKIA1234567890ABCDEF" in combined or
  "leaks found" in combined` where `combined = result.stdout + result.stderr`. The
  dual-channel check is intentional — gitleaks writes human-readable summary to
  stderr and JSON to the report-path file. **PASS.**

---

## Observations (No Action Required)

1. `_gitleaks_available()` is evaluated at module collection time (Python evaluates
   `@pytest.mark.skipif(expr, ...)` immediately on import). In the unlikely event
   gitleaks becomes unavailable between collection and execution, the tests would
   not skip. This is a cosmetic concern with no practical impact.

2. The `--report-path source / "_report.json"` places the JSON output inside
   `tmp_path`. gitleaks writes this file after scanning, so it is not itself
   scanned. pytest's `tmp_path` cleanup removes it afterwards. No issue.

---

## Summary

All CRITICAL, HIGH, and MEDIUM checklist items pass. The single acknowledged
deviation (`subprocess.run` vs `shutil.which` for binary detection) carries no
correctness risk and was noted in the S03 report.

**Verdict: PASS — no fixes required.**
