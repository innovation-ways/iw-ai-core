# I-00088 — S03 Tests Report

## What was done

- Reworked `tests/unit/test_auto_merge_health.py` so mocked `subprocess.run` tests assert the full argv/kwargs contract used by the probe:
  - `bash`
  - `.../step_executor_lib.sh`
  - `auto_merge_resolve`
  - resolved `cli_tool`
  - resolved `model`
  - probe prompt in `input`
  - non-empty `env["WORKTREE_PATH"]`
- Preserved existing payload assertions (`runtime_reachable`, `error`, `cli_tool`, `model`) while strengthening them with semantic dispatch assertions.
- Added new integration coverage in `tests/integration/test_auto_merge_health_runtime.py` using real subprocess execution:
  - success path: fake `opencode` shim prints `OK`, captures argv + stdin, probe records reachable
  - failure path: fake `opencode` shim exits non-zero, probe records unreachable + non-empty error

## Files changed

- `tests/unit/test_auto_merge_health.py`
- `tests/integration/test_auto_merge_health_runtime.py`

## Verification

- Pre-flight gates:
  - `make format` ✅
  - `make typecheck` ✅
  - `make lint` ✅
- RED-proof command (integration file only):
  - `uv run pytest tests/integration/test_auto_merge_health_runtime.py -v` ✅ (2 passed)
- Targeted test command for touched files:
  - `uv run pytest tests/unit/test_auto_merge_health.py tests/integration/test_auto_merge_health_runtime.py -v` ✅ (11 passed)

## Issues / observations

- Manual RED reasoning confirmed: with pre-S01 invocation (`step_executor.sh --step-type ...`), the script exits before runtime dispatch (`Worktree not found or invalid: --agent`), the fake PATH shim is never invoked, capture evidence is missing, and the new integration test fails as intended.
- Both pytest commands run with repo-default coverage settings; they report `ERROR: Coverage failure` because running file-scoped subsets cannot satisfy the global `fail_under=50%` threshold. Functional test results for the targeted files were fully green (2/2 and 11/11 passed).
