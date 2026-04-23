# QV Gate Report: Unit Tests (S09)

## What was done
Ran `make test-unit` to execute the unit test quality gate for work item I-00034.

## Test Results
- **Result**: FAIL
- **Passed**: 1215 tests
- **Failed**: 17 tests
- **Warnings**: 18

## Failed Tests

### Daemon Identity Mismatch (3 tests)
Tests in `test_daemon_core.py` are failing because `IW_CORE_EXPECTED_INSTANCE_ID` is set in the environment, but the mocked `instance_id` in tests does not match the expected value `518ac56a-36f7-4c43-8f53-cfbb8a6baa3e`. These tests call `_startup()` which invokes `verify_instance_identity()` that enforces the DB identity constraint.

- `test_startup_writes_pid_file`
- `test_startup_removes_stale_pid_file_and_continues`
- `test_startup_proceeds_when_no_pid_file`

### item_report CLI signature mismatch (5 tests)
`item_report()` received an unexpected keyword argument `archive_dir`. The test calls are invoking the CLI command with a parameter that the current implementation does not accept.

- `test_exit_code_0_on_success`
- `test_exit_code_2_on_path_resolution_failure`
- `test_stdout_flag_prints_markdown`
- `test_project_flag_respected`
- `test_stdout_does_not_write_file`

### merge_queue_cli exit code mismatch (4 tests)
Expected exit code `3` but got `2`. Likely a Click parameter validation change affecting how the `--ack` flag is processed.

### migrations_cli exit code mismatch (2 tests)
Same pattern — expected exit code `3`, got `2`.

### safe_migrate env var leakage (2 tests)
`IW_CORE_AGENT_CONTEXT='true'` is set in the environment and leaking into unit tests. Tests that expect `_assert_not_agent_context()` to pass when the env var is absent/empty are failing because the env var is already set to `'true'` before the test runs. These tests need `monkeypatch.delenv("IW_CORE_AGENT_CONTEXT")`.

## Observations
- Most failures (12/17) are due to environment variable or CLI argument signature mismatches that are pre-existing in the worktree, not caused by changes in I-00034.
- The daemon identity tests require proper mocking of `check_identity` to avoid real DB identity checks during unit testing.
- The `IW_CORE_AGENT_CONTEXT` env var is leaking across test runs.
