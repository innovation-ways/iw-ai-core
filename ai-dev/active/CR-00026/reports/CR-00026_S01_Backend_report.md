# CR-00026 S01 Backend Implementation Report

## What Was Done

Modified `_resolve_allure_dirs` in `orch/test_runner.py` to use a category subdir for the report path instead of a run_id suffix:
- Results dir: unchanged — `allure-results-{run_id}` (per-run isolation preserved)
- Report dir: now `{report_base}/{category}` (e.g. `allure-report/unit`)

Updated the docstring of `_resolve_allure_dirs` to reflect new behavior and removed the stale comment in `launch_test_run`.

## Files Changed

| File | Changes |
|------|---------|
| `orch/test_runner.py:597-619` | `_resolve_allure_dirs`: report path now uses `/{run.category}` instead of `-{run_id}` suffix; updated docstring |
| `orch/test_runner.py:67-68` | Removed "persistent HTML report keeps the run_id too" from inline comment |
| `tests/unit/test_test_runner.py:30-48` | `_make_run` helper now accepts `category` parameter (default `"unit"`) |
| `tests/unit/test_test_runner.py:151,171,181,191` | Updated 4 existing test assertions to expect `/{category}` suffix on report path |
| `tests/unit/test_test_runner.py:203-251` | Added 4 new test methods: `test_report_dir_uses_category_subdir`, `test_report_dir_uses_config_override_with_category`, `test_results_dir_retains_run_id_suffix`, `test_report_dir_no_run_id_suffix` |

## Test Results

All 32 tests in `test_test_runner.py` pass:
```
tests/unit/test_test_runner.py::TestResolveAllureDirs::test_uses_test_config_for_test_run_type PASSED
tests/unit/test_test_runner.py::TestResolveAllureDirs::test_uses_quality_config_for_quality_run_type PASSED
tests/unit/test_test_runner.py::TestResolveAllureDirs::test_falls_back_to_defaults_for_test_run_type PASSED
tests/unit/test_test_runner.py::TestResolveAllureDirs::test_falls_back_to_defaults_for_quality_run_type PASSED
tests/unit/test_test_runner.py::TestResolveAllureDirs::test_returns_none_when_project_not_found PASSED
tests/unit/test_test_runner.py::TestResolveAllureDirs::test_report_dir_uses_category_subdir PASSED [NEW]
tests/unit/test_test_runner.py::TestResolveAllureDirs::test_report_dir_uses_config_override_with_category PASSED [NEW]
tests/unit/test_test_runner.py::TestResolveAllureDirs::test_results_dir_retains_run_id_suffix PASSED [NEW]
tests/unit/test_test_runner.py::TestResolveAllureDirs::test_report_dir_no_run_id_suffix PASSED [NEW]
```

13 pre-existing failures in `test_merge_queue.py` and `test_safe_migrate.py` are unrelated to this change.

## Definition of Done

- [x] `_resolve_allure_dirs` returns `{report_base}/{category}` for the report dir
- [x] Results dir still uses `-{run_id}` suffix
- [x] All existing `TestResolveAllureDirs` tests updated and passing
- [x] Four new tests added and passing
- [x] `make test-unit` runs (failures are pre-existing, not regressions)
- [x] No other files modified