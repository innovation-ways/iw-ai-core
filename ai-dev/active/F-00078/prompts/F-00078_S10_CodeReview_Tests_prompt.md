# F-00078_S10_CodeReview_Tests_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Step Being Reviewed**: S09 (tests-impl)
**Review Step**: S10

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

See S01 prompt. Same rules apply.

## Input Files

- `uv run iw item-status F-00078 --json`
- `ai-dev/active/F-00078/F-00078_Feature_Design.md`
- `ai-dev/work/F-00078/reports/F-00078_S09_Tests_report.md` -- Includes the AC↔test coverage matrix
- All test files listed in S09's `files_changed`
- `tests/CLAUDE.md`

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S10_CodeReview_report.md`

## Context

Review the test additions for F-00078. The S09 step filled coverage gaps across:
- `orch/self_assess.py` parser + helpers (unit).
- `projects.toml` flag round-trip (integration).
- `batch_manager` soft-step semantics (integration).
- `iw step-done --analysis-json` (integration).
- Dashboard fragment render (TestClient).
- Skill body invariants (unit).

Critical to catch:
- Coverage gaps for ACs / Boundary Behavior rows / Invariants (the matrix from S09's report is the easiest cross-check).
- Tests that mock the DB in integration tests (forbidden by `tests/CLAUDE.md`).
- Tests with `importlib.reload(orch.config)` (forbidden).
- Tests that pass for the wrong reason (e.g., a regex that matches both passing and failing states).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations → CRITICAL `category: conventions`.

## Review Checklist

### 1. Coverage matrix

- Open S09's report; locate the AC↔test coverage matrix.
- For each AC, Boundary Behavior row, and Invariant in the design doc, verify there's at least one test mapping to it.
- Verify each mapped test actually exercises the behavior (not just imports the right module).
- Missing mapping for an AC → MEDIUM_FIXABLE per missed AC; missing mapping for an Invariant → HIGH per missed Invariant.

### 2. Test isolation rules (`tests/CLAUDE.md`)

- Integration tests MUST use testcontainers — `grep -n 'live\|5433\|getenv.*IW_CORE_DB' tests/integration/test_*self_assess*` should not show direct live-DB connections.
- Dashboard tests MUST use `TestClient`, not `requests.get`. `grep -n 'requests\.' tests/dashboard/test_*self_assess*` should not match.
- No `importlib.reload(orch.config)` anywhere in the new tests. CRITICAL if found.

### 3. Test correctness — common pitfalls

- **Truthy-string trap**: For the projects.toml non-bool tests, the test must explicitly use `caplog` to assert the warning was logged. `assert config.self_assess_enabled is False` alone isn't enough — bool coercion bugs can land at False for the wrong reason.
- **Soft-step regression guard**: The negative test (`implementation` step with `failed` does NOT progress) is critical. If it's missing, HIGH finding.
- **Dashboard XSS test**: The test must assert the escaped form is in the response (e.g., `&lt;script&gt;`), not just that the literal string appears. If the test does `assert "<script>" in response.text`, that's a false-pass — CRITICAL.
- **Findings file race**: The dashboard test must write the JSON file BEFORE making the request. If it writes after, the section won't render and the test's `assertIn("Self-Assessment", ...)` fails — but if the test instead asserts NOT in (negative test), it's a false-pass. Read the test carefully.
- **No mocked DB in integration tests**: `mock.patch.object(SessionLocal, ...)` or `MagicMock(spec=Session)` in `tests/integration/` is a CRITICAL violation per `tests/CLAUDE.md`.

### 4. Skill file tests

- The skill-files test should grep for forbidden patterns rather than assert on a hash (hashes are brittle).
- The "byte-identical synced copies" test is acceptable, but if the project's skills sync command transforms content (e.g., strips frontmatter), the test must call the sync function rather than compare files directly.

### 5. Coverage threshold

- If S09's report claims `orch/self_assess.py` coverage ≥ 90%, run `pytest --cov=orch.self_assess tests/unit/test_self_assess.py` to verify.
- If actual coverage < claimed, MEDIUM_FIXABLE.

### 6. Test naming and clarity

- Test names follow `test_<noun>_<predicate>` (e.g., `test_flag_absent_defaults_false`). Vague names like `test_self_assess_basic` are MEDIUM_FIXABLE.
- Each test has at most ONE assertion area (multiple asserts are fine, but they should all relate to one behavior).

### 7. Out-of-scope changes

- Tests should NOT modify production code. If S09 changed anything in `orch/`, `dashboard/`, `skills/`, or `templates/design/` to make a test pass, that's a HIGH finding (raise blocker, don't fix it during tests).

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass. The new test files MUST be discovered and run (not silently skipped). If a test is `@pytest.mark.skip`'d without a documented reason, MEDIUM_FIXABLE.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | XSS test passes on un-escaped output (false-pass); mocked DB in integration; importlib.reload | Must fix |
| **HIGH** | Missing test for an Invariant; missing soft-step regression guard; production code changed during S09 | Must fix |
| **MEDIUM (fixable)** | Vague test names; missing caplog assertion; coverage threshold not met | Should fix |
| **MEDIUM (suggestion)** | Better fixture reuse opportunity | Optional |
| **LOW** | Naming nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-impl",
  "work_item": "F-00078",
  "step_reviewed": "S09",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "...",
  "notes": "Include your own AC↔test coverage matrix verification result."
}
```
