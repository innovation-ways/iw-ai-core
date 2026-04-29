# I-00049 S01 Backend Report

## Summary

Fixed two bugs causing daemon freezes during QV baseline gate execution.

## Changes Made

### 1. `orch/daemon/batch_manager.py` — Fixed `_run_gate_command` pipe deadlock

**Problem**: `subprocess.run(capture_output=True)` on timeout only kills the shell process; grandchild processes (e.g., testcontainers from `make test-integration`) survive and hold pipe FDs open, causing `communicate()` to block forever.

**Fix**: Replaced `subprocess.run` with `subprocess.Popen` + `start_new_session=True` so the entire process tree is in its own process group. On `TimeoutExpired`, `os.killpg()` kills the entire group before draining pipes.

Key implementation details:
- Uses `contextlib.suppress(ProcessLookupError)` per ruff SIM105 suggestion
- Returns partial output on timeout (does not raise), allowing `_compute_qv_baselines` to log/store results
- Added `import contextlib`, `import os`, `import signal` at module level

### 2. `orch/daemon/qv_baseline.py` — Removed `integration-tests` from `GATE_PARSERS`

**Problem**: `integration-tests` was registered as a valid baseline gate, allowing `make test-integration` (which starts testcontainers) to be scheduled during worktree setup — an operation too slow for daemon setup.

**Fix**: Removed `"integration-tests": parse_pytest` from `GATE_PARSERS`. The existing "Unknown gate" code path in `_compute_qv_baselines` will log a warning and skip the gate safely.

### 3. `tests/unit/orch/daemon/test_qv_baseline.py` — Updated test

Updated `test_integration_tests_maps_to_parse_pytest` → `test_integration_tests_is_not_in_gate_parsers` to verify the correct new behavior.

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/batch_manager.py` | Replaced `subprocess.run` with `Popen` + process-group kill |
| `orch/daemon/qv_baseline.py` | Removed `integration-tests` from `GATE_PARSERS` |
| `tests/unit/orch/daemon/test_qv_baseline.py` | Updated test to verify `integration-tests` is absent |

## Quality Verification

| Check | Result |
|-------|--------|
| `make lint` (modified files) | Pass |
| `make typecheck` (modified files) | Pass |
| `make test-unit` | 1963 passed, 2 skipped |

## Notes

- The format check (`make format`) showed drift in unrelated files (`CR-99025`, `CR-99026`, `test_mapgen_mermaid.py`) not touched by this fix
- All modified files pass lint and typecheck individually
- Unit tests pass with zero failures