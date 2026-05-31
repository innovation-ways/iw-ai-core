# I-00121 S01 — Backend Report

## Summary

Fixed the root cause of missing Allure reports and NULL summaries for `make`-based test categories in `orch/test_runner.py`. The fix extracts the command-rewrite logic into a pure helper, injects `PYTEST_ADDOPTS` for `make` commands so pytest emits Allure results regardless of Makefile target, and gates `run.allure_report_dir` persistence on successful report generation.

## Files Changed

| File | Change |
|------|--------|
| `orch/test_runner.py` | 3 edits: (a) extracted `_build_run_command` helper at module level; (b) called helper in `launch_test_run` replacing inline logic; (c) gated `run.allure_report_dir` assignment on `_generate_allure_report` return value |
| `tests/unit/test_test_runner_allure_env.py` | New: 10 unit tests for `_build_run_command` covering make/pytest-direct/passthrough branches |

## What Was Done

### Requirement 1 — Extract pure helper `_build_run_command`

The inline Allure redirect logic (lines 86–92 in the original) was moved to a module-level function defined before `launch_test_run`:

```python
def _build_run_command(command: str, allure_results: str | None, execution_dir: str) -> str:
    ...
```

Three branches:
- `allure_results is None` → return command unchanged
- `"--alluredir" in command` → rewrite inline flag to run-scoped relative path
- `"make " in command` → prefix `ALLURE_RESULTS=<rel>` (existing) **plus** `PYTEST_ADDOPTS='--alluredir=<rel> $PYTEST_ADDOPTS'` (new)

### Requirement 2 — `PYTEST_ADDOPTS` injection for `make` commands (PRIMARY FIX)

```python
if "make " in command:
    return (
        f"ALLURE_RESULTS={results_rel} "
        f"PYTEST_ADDOPTS='--alluredir={results_rel} $PYTEST_ADDOPTS' "
        f"{command}"
    )
```

Properties:
- Run-scoped relative results dir (`allure-results-42`) appears inside `--alluredir` in `PYTEST_ADDOPTS`
- Append-safe: `$PYTEST_ADDOPTS` references the existing shell variable, preserving any pre-existing value
- Single-quoted value prevents word-splitting on spaces
- `PYTEST_ADDOPTS` NOT added for the pytest-direct branch (would duplicate `--alluredir`)

### Requirement 3 — `allure_report_dir` persistence only after report generation (SECONDARY FIX)

Before: `run.allure_report_dir = allure_report` was set unconditionally at lines 70–71, before the run executes.

After: the assignment was removed from the pre-run block and moved into the post-run block, gated on `_generate_allure_report` returning `True`:

```python
report_ok = _generate_allure_report(allure_results, allure_report, execution_dir)
if report_ok:
    run.allure_report_dir = allure_report
```

`run.allure_results_dir` remains assigned where it was (it is the working dir during the run). `parse_allure_summary` is still called only when `report_ok` is True (via the conditional).

## Quality Runs — No Dashboard Dependency

Confirmed: `dashboard/routers/quality.py` contains zero references to `allure_report_dir` or `allure_results_dir`. The quality router's `quality_runs` fragment and `launch_quality_gate` / `launch_quality_gate_fix` endpoints do not depend on these columns. After this change quality runs will have NULL `allure_report_dir` (instead of a dangling path), which is strictly more correct and causes no regression.

## Test Results

```
uv run pytest tests/unit/test_test_runner_allure_env.py tests/unit/test_test_runner.py -v
42 passed, 0 failed
```

New tests (all 10 pass):
- `test_make_command_injects_pytest_addopts_alluredir`
- `test_make_command_preserves_existing_pytest_addopts`
- `test_make_command_quote_safety`
- `test_make_command_with_alluredir_flag_takes_pytest_branch`
- `test_pytest_direct_command_rewrites_alluredir_without_addopts`
- `test_pytest_alluredir_equals_rewritten`
- `test_pytest_alluredir_space_separated_rewritten`
- `test_command_without_allure_flag_or_make_is_unchanged`
- `test_no_allure_results_returns_unchanged`
- `test_no_allure_results_preserves_pytest_direct`

Existing `test_test_runner.py` tests: 32 passed (all regression checks intact).

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ fixed `tests/unit/test_test_runner_allure_env.py` (1 file reformatted), all 977 files now formatted |
| `make typecheck` | ✅ Success: no issues found in 287 source files |
| `make lint` | ✅ All checks passed |

## TDD Evidence

**RED (first run, before implementation)**:
```
tests/unit/test_test_runner_allure_env.py::TestBuildRunCommandMake::test_make_command_injects_pytest_addopts_alluredir
ImportError: cannot import name '_build_run_command' from 'orch.test_runner'
```
The helper did not yet exist — `_build_run_command` was defined inline in `launch_test_run`.

**GREEN (after implementation)**: all 10 tests pass in 0.24s.

## Blockers

None.

## Notes

- The existing `TestLaunchTestRunCommandRewrite` tests in `test_test_runner.py` still test the full `launch_test_run` flow with the mock Popen capture — they confirm the *end-to-end* rewrite contract is preserved. The new `test_test_runner_allure_env.py` tests cover the pure helper contract.
- `_build_run_command` was intentionally placed before `launch_test_run` in the source file (line 37 vs. line 64) so Python resolves the name at call time without forward-reference issues.
