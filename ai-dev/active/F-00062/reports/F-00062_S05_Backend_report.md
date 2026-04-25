# F-00062 S05 Backend Report

## What Was Done

S05 wired the per-worktree container lifecycle primitives (built in S03 via `orch/daemon/worktree_compose.py`) into the daemon's batch lifecycle:

1. **Lifecycle hooks in `orch/daemon/batch_manager.py`** (`_launch_item`):
   - After `worktree_setup.sh` succeeds, check `has_iw_config(worktree_path)`. If False, set compose fields to NULL (legacy mode).
   - If True: call `load_config()` then `up()`. On success, persist `worktree_compose_path`, `worktree_db_port`, `worktree_app_port`. On failure, transition to `setup_failed` and call `down()`.
   - `WorktreeSetupError` now transitions to `setup_failed` (not `failed`) to distinguish setup failures from step execution failures.

2. **`worktree_compose.down()` on terminal states** (`orch/daemon/merge_queue.py`):
   - Added `down()` call before `_cleanup_worktree` in the `merged` success path.
   - Added `down()` call in `migration_rebase_failed`, `migration_invalid`, and merge failure exception handlers.

3. **`TERMINAL_BATCH_ITEM_STATUSES` constant** (`orch/db/models.py`):
   - Defined `TERMINAL_BATCH_ITEM_STATUSES` frozenset and `is_terminal_batch_item_status()` helper.

4. **Reaper module** (`orch/daemon/worktree_reaper.py`):
   - `scan()`: runs `docker ps -a --filter label=iwcore.role`, parses JSON output.
   - `classify()`: looks up `BatchItem` by `id` (PK), classifies as active/stale/orphan/malformed.
   - `reap()`: scans → classifies → calls `worktree_compose.down()` for stale/orphan/malformed, emits DaemonEvent.

5. **Reaper invocation** (`orch/daemon/main.py`):
   - Startup: `_reap_orphan_containers()` called before main poll loop.
   - Periodic: `_reap_orphan_containers()` called every 5 poll cycles.
   - Daemon-restart re-attach: `_reattach_worktrees()` queries non-terminal BatchItems with compose_path set, checks `is_alive()`, logs re-attach or missing stack.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `TERMINAL_BATCH_ITEM_STATUSES` constant and `is_terminal_batch_item_status()` helper |
| `orch/daemon/batch_manager.py` | Added compose up/down lifecycle hooks in `_launch_item`; setup failure → `setup_failed` |
| `orch/daemon/merge_queue.py` | Added `worktree_compose.down()` calls on terminal state transitions (merged, migration_rebase_failed, migration_invalid, failed) |
| `orch/daemon/main.py` | Added reaper invocation at startup + periodic (every 5 cycles); daemon-restart re-attach logic |
| `orch/daemon/worktree_reaper.py` | New module: `scan()`, `classify()`, `reap()` |
| `tests/unit/test_batch_manager.py` | Updated test to expect `setup_failed` instead of `failed` |
| `tests/unit/test_merge_queue.py` | Updated test to mock `worktree_compose.down()` |
| `tests/unit/daemon/test_worktree_reaper.py` | New file: reaper unit tests |
| `tests/unit/daemon/test_batch_manager_worktree_hooks.py` | New file: batch manager lifecycle hook tests |

## Test Results

- **1519 unit tests passed** (including 15 new tests for S05)
- **Lint**: All modified/new files pass ruff checks
- **Quality**: All checks pass (pre-existing TC003 in `worktree_compose.py` not modified)

## Notes

- **Reaper as separate module**: Decided to keep `worktree_reaper.py` separate from `worktree_compose.py` for cohesion. The reaper is a distinct concern (scanning, classification, orchestration) from the compose primitives (up, down, is_alive).
- **AC5 re-attach**: Implemented in `_reattach_worktrees()` which logs re-attached stacks and missing stacks. `is_alive()` is called but `up()` is NOT called for re-attached items, ensuring no duplicate `phase='up'` event.
- **BatchItemStatus.setup_failed**: Used for setup failures (instead of `failed`) to distinguish worktree creation failures from step execution failures. The state machine already had `setup_failed` defined.
- **Terminal state `down()` coverage**: Covered for all terminal transitions in `merge_queue.py` (merged, migration_rebase_failed, migration_invalid, failed) and in `_launch_item` (setup_failed). Items marked `failed` due to dependency blocking in `_process_batch` never had compose up called (they never left pending), so no `down()` needed.
