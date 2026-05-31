# I-00121 S04 — CodeReview (Tests) Report

## Summary

Reviewed S03's test coverage for I-00121 (Allure reports & summaries missing for `make`-based test categories). All quality gates pass. All 13 tests pass. Zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.

## Pre-Flight Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 978 files already formatted |

## Test Results

```
uv run pytest tests/unit/test_test_runner_allure_env.py tests/integration/test_test_runner_report_persistence.py -v
13 passed, 2 warnings in 5.31s
```

## Checklist

### 1. Reproduction test targets the bug ✅

`test_make_command_injects_pytest_addopts_alluredir` — this test would FAIL before the S01 fix: pre-fix `_build_run_command` for `make` commands only exported `ALLURE_RESULTS=<rel>` without `PYTEST_ADDOPTS`, so pytest inside any make target never received `--alluredir`. After S01 (adding `PYTEST_ADDOPTS='--alluredir=<rel> $PYTEST_ADDOPTS'`), the test passes. The assertion is on the specific value `--alluredir=allure-results-42` that must reach pytest — not merely "PYTEST_ADDOPTS appeared".

### 2. Semantic correctness, not shape ✅

Unit tests:
- `test_make_command_injects_pytest_addopts_alluredir`: asserts exact run-scoped value `--alluredir=allure-results-42` (not just "PYTEST_ADDOPTS is present").
- `test_make_command_preserves_existing_pytest_addopts`: asserts `$PYTEST_ADDOPTS` is referenced — regression for append-safety.
- `test_make_command_quote_safety`: asserts `'--alluredir=` (single-quoted delimiter) — regression for shell tokenisation.
- `test_pytest_direct_command_rewrites_alluredir_without_addopts`: asserts exact `--alluredir=allurel-results-42` rewritten inline AND `PYTEST_ADDOPTS=` is absent — no double `--alluredir`.
- `test_pytest_alluredir_equals_rewritten` / `test_pytest_alluredir_space_separated_rewritten`: both `--alluredir=<val>` and `--alluredir <val>` forms.

Integration tests:
- `test_report_dir_set_when_results_exist_and_report_generated`: asserts `run.allure_report_dir == expected_report_dir` (the specific path, not just "is not None") and `run.summary == fake_summary` (exact parsed structure, not just "is truthy").
- `test_report_dir_null_when_no_results_dir`: asserts `run.allure_report_dir is None` — the dangling-pointer assertion is verified via a fresh session query after `launch_test_run` commits, not a mock-only check.

No assertion would still pass if the fix regressed.

### 3. Coverage completeness ✅

- Both command shapes: `make` (TestBuildRunCommandMake) and pytest-direct (TestBuildRunCommandPytestDirect).
- Passthrough/no-op case: TestBuildRunCommandPassthrough.
- Append-safety: `test_make_command_preserves_existing_pytest_addopts` checks `$PYTEST_ADDOPTS` reference.
- Both persistence cases: (a) results dir + report generated → dir set + summary populated; (b) no results dir → dir NULL + `_generate_allure_report` not called (guarded by `if report_ok: run.allure_report_dir = ...` in production).
- Quality-run guard: `test_quality_run_never_sets_report_dir` — results dir created but quality guard blocks report generation, `allure_report_dir` stays NULL.

### 4. testcontainers + isolation rules ✅

- `test_test_runner_report_persistence.py` uses the `db_session` fixture (testcontainer-backed PostgreSQL, never port 5433).
- psycopg2 URL replacement: handled via `session_bind` extraction pattern (not the raw testcontainers URL — the test works with the bound engine directly).
- FTS DDL: delegated to `db_session` fixture (conftest.py runs FTS DDL after `create_all`).
- No `importlib.reload(orch.config)` — deferred import pattern inside test functions.
- No real subprocess / real `allure generate`: `subprocess.Popen`, `_generate_allure_report`, and `parse_allure_summary` are all monkeypatched.
- `_reset_session_cache()` pattern ensures each test gets a fresh engine on its own clone.
- Tests are deterministic and isolated.

### 5. File placement ✅

- `tests/unit/test_test_runner_allure_env.py` — pure-function unit tests (no I/O, no DB).
- `tests/integration/test_test_runner_report_persistence.py` — DB-backed integration test.

### 6. Scope ✅

Directional diff `git diff main...HEAD --name-only` shows changes in `ai-dev/active/I-00121/**` (design/docs for this item) plus the two test files and unrelated dashboard files from other worktrees. The two test files are the only new test code. `ai-dev/active|work/I-00121/**` is scope-preserving (it's this item's own directory, not scope creep).

## Findings

None.

## Verdict

**pass** — zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.