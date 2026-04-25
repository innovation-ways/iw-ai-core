# F-00062_S06_CodeReview_report

## Step Summary
Reviewed S05 (backend-impl) daemon-side lifecycle wiring: worktree_reaper, worktree_compose lifecycle, batch_manager hooks, and daemon integration.

## Files Reviewed
- `orch/daemon/worktree_reaper.py` (new - 229 lines)
- `orch/daemon/worktree_compose.py` (extended - 802 lines)
- `orch/daemon/batch_manager.py` (modified - lifecycle hooks in _launch_item)
- `orch/daemon/main.py` (modified - _reap_orphan_containers, _reattach_worktrees)
- `tests/unit/daemon/test_worktree_reaper.py` (new - 10 tests)
- `tests/unit/daemon/test_worktree_compose.py` (extended - 28 tests)
- `tests/unit/daemon/test_batch_manager_worktree_hooks.py` (new - 4 tests)

## Test Results
- All 32 S05-specific tests pass (10 reaper + 28 worktree_compose + 4 batch_manager hooks)
- Full unit suite: 1519 passed, 0 failed
- `make lint`: 11 pre-existing E501 errors (in test files unrelated to S05)
- `make quality`: ruff check on S05 files shows 1 TC003 (import organization) in worktree_compose.py - pre-existing

## Checklist Findings

### 1. Lifecycle Hook Completeness
**TERMINAL_BATCH_ITEM_STATUSES** constant in `orch/db/models.py:157` is the single source of truth.

Terminal transitions verified:
- `merged`: `merge_queue.py:214` → `down()` at line 223 ✓
- `failed` (merge error): `merge_queue.py:266` → `down()` at line 269 ✓
- `migration_invalid`: `merge_queue.py:179` → `down()` at line 185 ✓
- `migration_rebase_failed`: `merge_queue.py:144` → `down()` at line 150 ✓
- `setup_failed`: `batch_manager.py:334,360` → `down()` at line 357 ✓

**Note on dependency-failure path** (`batch_manager.py:179`): Items marked `failed` due to dependency failure were `pending` (compose never brought up), so no `down()` call is needed. The reaper safety net handles any edge case.

### 2. Reaper Classification Correctness
- `classify()` in `worktree_reaper.py:129` correctly: returns `malformed` for None/non-numeric batch_item_id, `orphan` for missing BatchItem, `stale` for terminal BatchItem, `active` otherwise.
- Malformed labels (empty `iwcore.batch_item=`) → `malformed` → reaped ✓
- Uses `TERMINAL_BATCH_ITEM_STATUSES` (single source of truth) ✓
- `archived`/`restarted_discarded` are NOT in `BatchItemStatus` enum - correctly excluded ✓

### 3. Race Conditions
- The "reap only if container >10s old" mitigation is NOT implemented in code. However, the lifecycle path in `batch_manager._launch_item()` commits the BatchItem row BEFORE calling `worktree_compose.up()`, satisfying the alternative mitigation. Verified at `batch_manager.py:325` (batch_item status committed before `up()`). ✓

### 4. Daemon-Restart Re-attach
- `main.py:_reattach_worktrees()` queries non-terminal items with `worktree_compose_path IS NOT NULL` ✓
- Does NOT call `up()` for alive stacks (AC5) ✓
- Logs missing stacks and lets next poll cycle handle ✓

### 5. Idempotency
- `down()` in `worktree_compose.py:699` is idempotent - `down -v --remove-orphans` handles already-torn-down stacks ✓
- `up()` guarded by `BatchItemStatus.setting_up → executing` transition ✓
- Reaper safe to run repeatedly ✓

### 6. DaemonEvent Emission
- All lifecycle actions emit events via `_emit_daemon_event()` helper with `event_metadata` (correct Python attribute) ✓
- Reaper emits per-reap event with classification info ✓

### 7. Docker Off-Limits Policy
All docker invocations correctly isolated to `orch/daemon/worktree_compose.py` (the designated module per policy). `main.py` and `batch_manager.py` call `worktree_compose.down()` and `worktree_compose.up()` only - no direct docker calls. ✓

## Mandatory Fix Count: 0

## Verdict: PASS
