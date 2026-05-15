# I-00085_S03_Tests_prompt

**Work Item**: I-00085 — .mypy_cache triggers gitleaks false positives
**Step**: S03
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/I-00085/I-00085_Issue_Design.md` — see "Test to Reproduce" (full test code) and AC1/AC2/AC3
- `ai-dev/work/I-00085/reports/I-00085_S01_Pipeline_report.md`
- `tests/CLAUDE.md`
- `.gitleaks.toml` — read this BEFORE writing the negative test so you
  know which patterns/paths the project already allowlists

## Output Files

- `tests/integration/test_security_secrets_cache_independence.py` (new file)
- `ai-dev/work/I-00085/reports/I-00085_S03_Tests_report.md`

## Context

Two tests minimum — both **isolated** via `tmp_path` (see the design
doc's "Test to Reproduce" section for the canonical implementation):

1. **Reproduction test (AC1, AC2)** — Build a synthetic
   `<tmp_path>/.mypy_cache/3.12/threading.data.json` containing the
   string that CR-00053's S16 actually flagged (`threading.local` —
   matches the `iw-internal-fqdn` custom rule). Run gitleaks against
   `<tmp_path>` with `--config <project>/.gitleaks.toml`. Assert
   `returncode == 0`. **This test FAILS against pre-S01
   `.gitleaks.toml` and PASSES post-S01** — that is the TDD RED→GREEN
   transition.

2. **Control test (AC3) — over-broad-allowlist guard** — Create
   `<tmp_path>/leak_target/config.py` containing the string
   `AKIA1234567890ABCDEF` (an AWS-shaped key that matches the
   built-in `aws-access-token` rule). Run gitleaks. Assert
   `returncode != 0` AND the offending key appears in stdout. This
   test passes pre- and post-fix; it exists to flag a future
   maintainer who tries to broaden the allowlist to something like
   `\.cache/` or `cache/`.

### Allowlist pitfalls — DO NOT trip these

- `.gitleaks.toml` already allowlists **`tests/fixtures/`** as a path
  AND **`AKIAIOSFODNN7EXAMPLE`** as a regex. Do NOT plant the negative
  test's bad-secret in `tests/fixtures/`. Do NOT use the
  `AKIAIOSFODNN7EXAMPLE` pattern. Either choice silently suppresses
  the leak and the control test "passes" for the wrong reason.
- Plant the bad-secret in a non-allowlisted sandbox subdirectory like
  `leak_target/`. Use the AWS-shape `AKIA1234567890ABCDEF` (16 chars
  after `AKIA`; not the `EXAMPLE` suffix).
- Reminder: the project's allowlist regexes use `(?:^|/)tests/fixtures/`
  — they match anywhere in the path, so `<tmp_path>/tests/fixtures/...`
  is also allowlisted. Pick a fresh top-level dir name.

### `gitleaks` binary availability

- Both tests need the `gitleaks` binary on PATH (same dependency as
  `make security-secrets`).
- Guard each test with `pytest.importorskip` is wrong (it's not a
  Python module). Instead use:
  ```python
  if shutil.which("gitleaks") is None:
      pytest.skip("gitleaks binary not installed")
  ```
- Do this at the top of each test, not at module import time.

### CRITICAL: Semantic Correctness Over Shape Checking

- BAD: `assert "leaks" in result.stdout` (matches "no leaks found" too)
- GOOD: `assert result.returncode == 0` (positive test)
- BAD: `assert result.returncode != 0` alone (negative test — too weak)
- GOOD: `assert result.returncode != 0` AND `assert "AKIA1234567890ABCDEF" in result.stdout`

## TDD Requirement

The reproduction test must FAIL against pre-S01 `.gitleaks.toml` and
PASS after S01. Capture the failing run output in `tdd_red_evidence`
(or, if S01 has already landed in the worktree, run against the
pre-fix config by temporarily checking out the previous version via
`git show HEAD~1:.gitleaks.toml > /tmp/pre_fix.toml` — design-time
exercise only, do NOT include this in the test code itself).

The control test passes both pre- and post-fix; it is a regression
guard, not an RED test.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_security_secrets_cache_independence.py -v
```

Do NOT run `make test-integration` or `make test-unit` at large. The
QV gates do that downstream.

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
  "tdd_red_evidence": "Pre-fix run: pytest .../test_i00085_mypy_cache_does_not_trigger_false_positives — AssertionError: gitleaks returncode=1 (leaks found on threading.data.json)",
  "blockers": [],
  "notes": ""
}
```
