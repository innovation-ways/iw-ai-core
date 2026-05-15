# I-00085_S03_Tests_prompt

**Work Item**: I-00085 — .mypy_cache triggers gitleaks false positives
**Step**: S03
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/I-00085/I-00085_Issue_Design.md` — see "Test to Reproduce" and 3 ACs
- `ai-dev/work/I-00085/reports/I-00085_S01_Pipeline_report.md`
- `tests/CLAUDE.md`

## Output Files

- `tests/integration/test_security_secrets_cache_independence.py` (new file)
- `ai-dev/work/I-00085/reports/I-00085_S03_Tests_report.md`

## Context

Two tests minimum:

1. **Reproduction test (AC1, AC2)** — populate `.mypy_cache/` via `make
   type-check`, then run `make security-secrets`, assert exit 0.
2. **Negative test (AC3)** — add a fake real-secret-shaped string to a
   test fixture (e.g., `tests/fixtures/fake_secret_for_i00085.txt` with
   a string matching one of gitleaks's standard rules — but NOT a real
   credential). Run `make security-secrets`. Assert it FAILS / detects
   the secret. Then `git rm` the fixture in test teardown so it does not
   pollute the worktree.

### Important caveats

- The reproduction test mutates global project state (`.mypy_cache/`).
  Mark it appropriately or guard with `tmp_path` + a copy of the project
  if pytest-xdist parallelism would be unsafe.
- The negative test must NEVER commit a real secret. Use one of
  gitleaks's documented test patterns (e.g., a fake AWS key
  `AKIAIOSFODNN7EXAMPLE`).
- The negative test must clean up its fixture even on failure
  (try/finally or pytest fixture teardown).

### CRITICAL: Semantic Correctness Over Shape Checking

- BAD: `assert "leaks" in result.stdout`
- GOOD: `assert result.returncode == 0` AND `assert "leaks found: 0" in result.stdout`
- BAD: `assert result.returncode != 0` (negative test) — too weak
- GOOD: `assert result.returncode != 0` AND `assert "AKIA" in result.stdout`

## TDD Requirement

This step is the test step. The reproduction test must FAIL against
pre-S01 `.gitleaks.toml` and PASS after S01.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_security_secrets_cache_independence.py -v
```

Do NOT run `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00085",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/test_security_secrets_cache_independence.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed",
  "tdd_red_evidence": "n/a — S01 already applied; tests are the regression suite",
  "blockers": [],
  "notes": ""
}
```
