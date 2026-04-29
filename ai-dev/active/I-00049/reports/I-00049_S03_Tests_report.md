# I-00049_S03_Tests_report

## Step: S03 — Tests

## What Was Done

Created `tests/unit/test_i00049_gate_command.py` with 7 tests covering both parts of the I-00049 fix:

1. **Regression test for pipe deadlock** (`test_run_gate_command_does_not_deadlock_with_background_grandchild`): Verifies `_run_gate_command` returns promptly (elapsed < 5s) when the parent shell exits and a grandchild keeps the pipe FD open. Uses a mocked `Popen` whose `communicate()` raises `TimeoutExpired` on first call then drains on second call.

2. **Normal completion** (`test_run_gate_command_returns_stdout_on_success`, `test_run_gate_command_returns_output_on_nonzero_exit`): Verifies `_run_gate_command` returns output on exit 0 and on non-zero exit without raising.

3. **killpg on timeout** (`test_run_gate_command_kills_process_group_on_timeout`, `test_run_gate_command_returns_output_after_killpg`): Verifies `os.killpg` is called with `SIGKILL` and the correct PGID when `communicate()` times out.

4. **GATE_PARSERS second fix** (`test_integration_tests_not_in_gate_parsers`, `test_fast_gates_remain_in_gate_parsers`): Verifies `integration-tests` is NOT in `GATE_PARSERS` and the fast gates (`lint`, `typecheck`, `unit-tests`, `frontend-tests`) ARE still present.

## Files Changed

- `tests/unit/test_i00049_gate_command.py` — new test file (7 tests)

## Test Results

```
7 passed — all I-00049 tests clean
make test-unit: 1970 passed, 2 skipped
make lint: ok (only pre-existing errors in unrelated files)
make typecheck: ok
```

## Key Implementation Notes

- Used `MagicMock` with `__enter__.return_value = fake_proc` to properly simulate context manager protocol, since `subprocess.Popen` is used with `with`.
- Used `side_effect` list on `communicate` to simulate first raising `TimeoutExpired` then returning drained output on second call.
- Used `Path` from `pathlib` instead of `pytest.Path` for type annotations to avoid ruff TC002 (unused import).
- The real `_run_gate_command` is called in the regression test with a real working directory (`tmp_path`), so normal completion tests run against real subprocesses.

## Blockers

None.
