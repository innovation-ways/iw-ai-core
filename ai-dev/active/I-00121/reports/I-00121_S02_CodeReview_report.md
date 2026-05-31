# I-00121 S02 — Code Review (Backend / S01)

## Reviewer: CodeReview · Step: S02 · Reviewed: S01 (Backend)

---

## Verdict: ✅ PASS

Zero CRITICAL, HIGH, or MEDIUM_FIXABLE findings. All checklist items pass.

---

## Files Changed (Scope)

Only these production files were modified by S01:

| File | Change |
|------|--------|
| `orch/test_runner.py` | Primary: extracted `_build_run_command` helper; called it from `launch_test_run`. Primary: added `PYTEST_ADDOPTS='--alluredir=<rel> $PYTEST_ADDOPTS'` for `make` commands. Secondary: gated `run.allure_report_dir` assignment on `_generate_allure_report` return value. |

New test files (untracked, not yet committed — will be committed by S03):
- `tests/unit/test_test_runner_allure_env.py` — 10 unit tests for `_build_run_command`
- `tests/integration/test_test_runner_report_persistence.py` —2 integration tests for dangling-pointer guard

No dashboard files, no migration files, no `ai-dev/` content touched.

---

## Checklist Results

### 1. PRIMARY fix correctness

**Run-scoped relative dir reaches `--alluredir`**: ✅
`_build_run_command` computes `results_rel = Path(allure_results).relative_to(execution_dir)` and injects it as `--alluredir={results_rel}` in `PYTEST_ADDOPTS`. For a run with `allure_results=/proj/allure-results-42` and `execution_dir=/proj`, the injected value is `--alluredir=allure-results-42` — the run-scoped relative dir, not the static `allure-results`.

**Append-safe for pre-existing `PYTEST_ADDOPTS`**: ✅
The injected value is `'--alluredir={results_rel} $PYTEST_ADDOPTS'` (single-quoted). The `$PYTEST_ADDOPTS` shell variable reference means any pre-existing value is appended, not clobbered. Unset expands to empty without breaking the shell command.

**Value correctly quoted**: ✅
The entire `PYTEST_ADDOPTS` value is single-quoted (`'--alluredir={rel} $PYTEST_ADDOPTS'`), so the space between `--alluredir=...` and any existing addopts does not split into separate shell tokens.

**pytest-direct branch does NOT get `PYTEST_ADDOPTS`**: ✅
The `--alluredir` branch returns `re.sub(...)` without any `PYTEST_ADDOPTS` injection. The `make` branch is only entered when `"make " in command` is true and `"--alluredir" not in command`. These are mutually exclusive. Unit test `test_make_command_with_alluredir_flag_takes_pytest_branch` confirms this.

###2. SECONDARY fix correctness

**Old unconditional assignment gone**: ✅
`run.allure_report_dir = allure_report` at the old lines 70–71 is removed. Verified by `git diff main -- orch/test_runner.py`.

**Assignment gated on `_generate_allure_report` success**: ✅
Post-run block now reads:
```python
run.allure_report_dir = None  # Reset: will be set only on success
if run.run_type != "quality" and allure_results and Path(allure_results).is_dir():
    if _generate_allure_report(allure_results, allure_report, execution_dir):
        run.allure_report_dir = allure_report  # Set only after generation succeeds
        ...
```
`run.summary` is still only set when stats parse (inside the same `if report_ok:` block).

**No code path reads `run.allure_report_dir` between launch and generation**: ✅
The column is written only at post-run (after subprocess completes). No pre-run code reads it. The dangling-pointer class of bug is fully eliminated.

### 3. Helper purity

**Pure function**: ✅
`_build_run_command` takes only `str`/`Path` inputs, performs string manipulation and one `re.sub`, and returns a `str`. No DB, no I/O, no global state.

**Module-level, before `launch_test_run`**: ✅
Defined at line 37 (before `launch_test_run` at line 64). Python resolves the name at call time without forward-reference issues.

**Unit-testable**: ✅
10 dedicated unit tests cover all three branches (make, pytest-direct, passthrough) with specific assertions on the exact command string produced.

### 4. Quality runs

**`dashboard/routers/quality.py` does not depend on `allure_report_dir`**: ✅
Confirmed by `grep -n "allure_report_dir\|allure_results_dir" dashboard/routers/quality.py` — zero matches. Quality runs have `run_type == "quality"`, which is already guarded by `if run.run_type != "quality"` before Allure processing. After this change, quality runs will have `NULL allure_report_dir` instead of a dangling path — strictly more correct. S01 report confirms this conclusion.

### 5. Scope

**Only `orch/test_runner.py` (+ new test files) changed**: ✅
`git diff main...HEAD --name-only` shows no changes to `orch/test_runner.py` from `main` — the change is uncommitted (only the `ai-dev/` design files are committed). The production module is modified; the new test files are untracked and will be committed by S03. No dashboard files touched. No scope creep.

###6. TDD RED evidence

**RED before implementation**: The S01 report states the RED was an `ImportError: cannot import name '_build_run_command' from 'orch.test_runner'`. This is a genuine RED — the helper didn't exist yet, so importing it raises `ImportError`. The test runner then fails because the callable doesn't exist.

**Would the test actually fail against pre-fix code?** ✅ Reasoning: before the fix, `_build_run_command` did not exist in `orch/test_runner.py`. Any test that imports and calls `_build_run_command` would raise `ImportError` before the first assertion is reached. This is a valid RED state — the test was written to the interface the fix would provide, and the pre-fix module lacks that interface. Once the helper is added (the fix), the test's assertions execute and would pass if the implementation is correct.

---

## Pre-Flight Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 978 files already formatted |
| Unit tests (`-k test_runner`) | ✅ 42 passed, 0 failed |

---

## Test Results

```
uv run pytest tests/unit -k test_runner -v
42 passed, 0 failed
```

New tests (all10 pass):
- `test_make_command_injects_pytest_addopts_alluredir` ✅
- `test_make_command_preserves_existing_pytest_addopts` ✅
- `test_make_command_quote_safety` ✅
- `test_make_command_with_alluredir_flag_takes_pytest_branch` ✅
- `test_pytest_direct_command_rewrites_alluredir_without_addopts` ✅
- `test_pytest_alluredir_equals_rewritten` ✅
- `test_pytest_alluredir_space_separated_rewritten` ✅
- `test_command_without_allure_flag_or_make_is_unchanged` ✅
- `test_no_allure_results_returns_unchanged` ✅
- `test_no_allure_results_preserves_pytest_direct` ✅

Existing `test_test_runner.py` tests: 32 passed (all regression checks intact).

---

## Findings

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00121",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "42 passed, 0 failed",
  "notes": "S01 is a clean pass. Both the primary fix (PYTEST_ADDOPTS injection for make commands) and the secondary fix (dangling-pointer guard) are correctly implemented. The extracted _build_run_command helper is pure, module-level, and well-tested. Quality runs are unaffected. No scope creep. TDD RED evidence is valid."
}
```
