# Step 08: Daemon Batch Manager & Merge Queue

## Context

Daemon core and step monitor are complete. Now implement the batch processing engine — the logic that launches work items, starts agent steps, and merges completed items.

Read these documents:
- `IW_AI_Core_Daemon_Design.md` — sections 4.2-4.7 (batch processing, item launch, step launch, step completion, merge queue, batch completion)

## Task

### 1. Batch Manager (`orch/daemon/batch_manager.py`)

Implement `BatchManager` class (one instance per project):

#### `process_batches()`
- Query batches with status `approved` or `executing`
- For `approved` batches: transition to `executing`, emit event
- For each executing batch: call `_process_batch()`

#### `_process_batch(batch)`
- Load all batch_items ordered by execution_group
- Count currently executing items (status in setting_up, executing)
- Determine current execution group (lowest group with pending/executing items)
- If no pending items → check batch completion
- Launch pending items up to `max_parallel` limit

#### `_current_execution_group(items) -> int | None`
- Returns the lowest group number that has non-terminal items
- Returns None if all items are in terminal state (merged, failed, skipped)

#### `_launch_item(batch, batch_item)`
- Phase 1: Set status to `setting_up`, call worktree setup script
- Phase 2: Set status to `executing`, record worktree_info, call `_launch_next_step()`
- On setup failure: mark as failed with error message

#### `_setup_worktree(item_id) -> dict`
- Call `executor/worktree_setup.sh` via `subprocess.run()` with timeout (300s)
- Return worktree metadata dict (path, branch, created_at)
- Raise `WorktreeSetupError` on non-zero exit

### 2. Step Launch Logic

#### `_launch_next_step(item_id, worktree_info)`
- Query next pending step for this item (ordered by step_number)
- If no pending steps → item completed, call `_complete_item()`
- Otherwise → call `_launch_step()`

#### `_launch_step(step, worktree_info)`
- Build command string based on cli_tool (opencode or claude)
- Determine timeout via `get_timeout()`
- Create log file path
- Launch process via `subprocess.Popen()` with `start_new_session=True` (critical: detach from daemon)
- Record EVERYTHING in `step_runs`: pid, command, worktree_path, cli_tool, timeout_secs, started_at, last_heartbeat
- Update `workflow_steps.status = 'in_progress'`
- Emit `step_launched` event

### 3. Step Completion Detection

The daemon doesn't directly detect when an agent finishes — the agent calls `iw step-done` which updates the DB. The daemon sees the updated status on the next poll cycle.

#### In `monitor_running_steps()` (extend from step 07):
After checking PID health, also check if the step status was updated to `completed` or `failed` by the agent (via `iw` CLI). If so:
- If `completed` → call `_on_step_completed()` which launches the next step
- If `failed` or `needs_fix` → leave for fix cycle logic or user action

#### `_complete_item(item_id)`
- Update `work_items.status = 'completed'`, `completed_at = now()`
- Update `batch_items.status = 'completed'`
- Emit `item_completed` event
- Item enters the merge queue (picked up by `process_merge_queue()`)

### 4. Merge Queue (`orch/daemon/merge_queue.py`)

#### `process_merge_queue()`
- Query batch_items with status `completed` (ready to merge), ordered by started_at
- Check if any item is currently `merging` — if so, wait (one merge at a time)
- Merge the oldest completed item

#### `_merge_item(batch_item)`
- Set status to `merging` (custom intermediate state for tracking)
- Call `executor/worktree_commit.sh` via `subprocess.run()` with timeout (120s)
- On success: status=`merged`, record merge_info, emit `item_merged`, cleanup worktree
- On failure: status=`failed`, emit `merge_conflict`

#### `_cleanup_worktree(item_id, worktree_path)`
- Call `git worktree remove` (or `rm -rf` + `git worktree prune`)
- Log cleanup

### 5. Batch Completion (`orch/daemon/batch_manager.py`)

#### `_check_batch_completion(batch, items)`
- All items merged → batch status `completed`, emit `batch_completed`
- All items in terminal state but some failed → `completed_with_errors`, emit event
- Otherwise → not done yet

### 6. Wire Into Daemon Main Loop

Update `Daemon._poll_cycle()` to call for each project:
1. `manager.monitor_running_steps()` (from step 07)
2. `manager.process_batches()` (new)
3. `manager.process_merge_queue()` (new)

### 7. Tests (TDD)

**Unit tests** (`tests/unit/test_batch_manager.py`):
- Test: execution group resolution (all pending → group 0; group 0 done → group 1)
- Test: parallelism limit respected (max_parallel=2, don't launch 3rd)
- Test: batch completion detection (all merged → completed, mixed → completed_with_errors)
- Test: command building (opencode vs claude)
- Test: step launch records all fields in step_run

**Unit tests** (`tests/unit/test_merge_queue.py`):
- Test: one merge at a time (second item waits)
- Test: merge failure marks item as failed
- Test: merge order is oldest first

**Integration tests** (`tests/integration/test_batch_manager.py`):
- Test: full batch lifecycle in DB — create items, create batch, approve, simulate step completion, verify merge queue order
- Test: execution groups advance correctly when group 0 all complete

## Acceptance Criteria

- [ ] Daemon picks up approved batches and launches items
- [ ] Steps are launched with PID, command, and worktree recorded in DB
- [ ] Completed items enter the merge queue
- [ ] Merges are sequential per project (one at a time)
- [ ] Batch completion is detected correctly
- [ ] `start_new_session=True` used on all subprocess.Popen calls (agents survive daemon restart)
- [ ] `make test` passes, `make quality` passes
