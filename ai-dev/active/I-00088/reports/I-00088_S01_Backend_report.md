# I-00088 — S01 Backend Report

## What was done

- Added a new RED-first unit test to assert the subprocess argv shape for the probe call path.
- Updated `orch/daemon/auto_merge_health.py` to invoke the canonical one-shot executor path:
  - `bash executor/step_executor_lib.sh auto_merge_resolve <cli_tool> <model>`
  - prompt passed via stdin (`PROBE_PROMPT` unchanged)
  - timeout preserved (`max(15, interval//4)`)
  - phase-0 and recent-probe skip guards preserved
  - success condition preserved (`returncode == 0 and "OK" in stdout`)
  - error handling preserved (`timeout` and generic exception formatting)
- Renamed `_EXECUTOR_PATH` to `_EXECUTOR_DIR` and added `os` import to build env.
- Preserved daemon event metadata contract unchanged (`runtime_reachable`, `cli_tool`, `model`, `probe_duration_ms`, `error`).

## Files changed

- `orch/daemon/auto_merge_health.py`
- `tests/unit/test_auto_merge_health.py`

## Test results

### TDD RED

- Command: `uv run pytest tests/unit/test_auto_merge_health.py -v`
- New test failed as expected:
  - `tests/unit/test_auto_merge_health.py::test_probe_invokes_executor_lib_with_resolved_runtime_and_model`
  - `AssertionError: assert '/bin/bash' == 'bash'`

### GREEN

- Re-ran: `uv run pytest tests/unit/test_auto_merge_health.py -v`
- Functional outcome: `9 passed` in the target file, including the new test.
- Note: pytest process exits non-zero because the repo-wide coverage fail-under gate triggers when running only this single file in isolation (`FAIL Required test coverage of 50.0% not reached`).

### Pre-flight quality gates

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Issues / observations

- No executor scripts were modified (as required).
- The probe now shares the same runtime invocation path as auto-merge resolve, preventing CLI-shape drift.
