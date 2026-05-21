# CR-00067 S07 — QV: Unit Test Suite

## What was done

Ran `make test-unit` as gate S07. The suite initially failed with one failing test:

```
FAILED tests/unit/daemon/test_worktree_reaper.py::TestReapIntegration::test_reaper_emits_daemon_event_per_reap_action
```

The test `test_reaper_emits_daemon_event_per_reap_action` asserted `db.add.assert_called_once()` but `db.add` was called **twice**:
1. Once for the `DaemonEvent` from the main `reap()` path (expected)
2. Once for the `DaemonEvent` from `reap_e2e_stacks(db)` called at the end of `reap()`

The second call is triggered by `scan_e2e_stacks()` which calls `docker compose ls --all --format json`. In the CI/test environment the `worktree_reaper` module-level `_E2E_COMPOSE_FILE` resolves to `.../.worktrees/CR-00067/docker-compose.e2e.yml`. When the subprocess returns actual system state (non-mocked), `reap_e2e_stacks` runs for real and calls `db.add` a second time.

The fix: added `patch("orch.daemon.worktree_reaper.scan_e2e_stacks", return_value=[])` to the test's context manager to fully isolate the test from the e2e stack sweep path.

## Files changed

| File | Change |
|------|--------|
| `tests/unit/daemon/test_worktree_reaper.py` | Added `patch("orch.daemon.worktree_reaper.scan_e2e_stacks", return_value=[])` to `test_reaper_emits_daemon_event_per_reap_action` to prevent the e2e stack sweep from emitting an additional `db.add` call |

## Test results

After the fix: **3332 passed**, 5 skipped, 5 xfailed, 2 xpassed, 46 warnings — **PASS**.

- Coverage: 52.45% (above 50.0% threshold)
- No other tests were affected

## Observations

- The `reap()` function unconditionally calls `reap_e2e_stacks(db)` at the end, which emits its own `DaemonEvent`. This is intentional (e2e stack sweeping) but wasn't isolated in the test.
- The regression was introduced when the e2e stack sweep was added to `reap()` — the existing test was not updated to mock the new call path.