# I-00049_S04_CodeReview_report

## Step: S04 — Code Review (S03 tests-impl)

## What Was Done

Reviewed `tests/unit/test_i00049_gate_command.py` (7 tests) against the S04 review checklist.

## Review Checklist Results

### 1. Reproduction test — semantic correctness and real coverage
- `test_run_gate_command_does_not_deadlock_with_background_grandchild` uses `MagicMock` with `side_effect=[TimeoutExpired, (b"", b"")]` to simulate the timeout → killpg → drain path
- Wall-clock assertion: `elapsed < 5.0` — tight enough to catch a regression
- Timeout is simulated via `side_effect`, not a real 300s wait (correct for unit tests)
- Would fail against old `subprocess.run` code because the mock patches `subprocess.Popen` specifically — old `subprocess.run` code path is replaced entirely by the fix

### 2. Process-group kill test — mock correctness
- `test_run_gate_command_kills_process_group_on_timeout` correctly asserts `mock_killpg.assert_called_once_with(12345, signal.SIGKILL)` — full signature check
- `__enter__`/`__exit__` mocks set up correctly for context manager protocol

### 3. GATE_PARSERS exclusion tests
- `test_integration_tests_not_in_gate_parsers` asserts `"integration-tests" not in GATE_PARSERS` with descriptive message
- `test_fast_gates_remain_in_gate_parsers` verifies `lint`, `typecheck`, `unit-tests`, `frontend-tests` remain

### 4. Normal and error path tests
- `test_run_gate_command_returns_stdout_on_success` asserts `"hello" in result` (actual content, not just non-empty)
- `test_run_gate_command_returns_output_on_nonzero_exit` verifies output returned without raising

### 5. Isolation and determinism
- Mock-based tests (`TestI00049RunGateCommandNonBlocking`, `TestRunGateCommandKillpgOnTimeout`) avoid flakiness
- Real subprocess used only in `test_run_gate_command_returns_stdout_on_success` (appropriate — exercises real code path)
- No filesystem, DB, or network dependencies

### 6. Test conventions
- File in `tests/unit/` ✓
- No testcontainers ✓
- Imports clean and sorted ✓

## Test Verification

```
tests/unit/test_i00049_gate_command.py: 7 passed
make test-unit: 1970 passed, 2 skipped
uv run ruff check tests/unit/test_i00049_gate_command.py: All checks passed!
make typecheck: Success: no issues found
```

Note: `make lint` shows 6 pre-existing errors in `test_safe_migrate.py`, `test_safe_migrate_guards.py`, and `test_merge_queue_migration_pipeline.py` — none in the new I-00049 test file.

## Files Changed

- `tests/unit/test_i00049_gate_command.py` — 7 tests reviewed (no changes needed)

## Verdict

**pass**

| Criterion | Result |
|-----------|--------|
| Mock-based reproduction test exercises fix code path | ✓ |
| Wall-clock assertion tight (< 5 s) | ✓ |
| `os.killpg` asserted with full signature `(pgid, SIGKILL)` | ✓ |
| GATE_PARSERS exclusion with meaningful message | ✓ |
| Normal/error paths assert actual content | ✓ |
| Isolation (mocks where appropriate, real subprocess sparingly) | ✓ |
| File location, no testcontainers, clean imports | ✓ |
| All I-00049 tests pass | ✓ (7/7) |
| Lint clean on new file | ✓ |
| Typecheck clean | ✓ |

## Notes

The reproduction test uses mocks rather than a real subprocess because a true reproduction of the pipe-deadlock scenario requires a real grandchild holding the pipe open for the full timeout duration (300s). The mock-based approach correctly tests the fix's code path (Popen + killpg on TimeoutExpired) and would fail if that code path were reverted to `subprocess.run`.
