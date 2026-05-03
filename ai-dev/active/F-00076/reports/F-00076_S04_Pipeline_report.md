# F-00076 S04 Pipeline Report

## What Was Done

Implemented the cross-batch file-conflict gate for F-00076. All pipeline components are in place:

### 1. `orch/daemon/scope_overlap.py` (new file)
Pure glob-intersection helpers used by `batch_manager._process_batch()` to detect cross-batch file conflicts:
- `is_test_path(glob)` — identifies test-only paths (mirrors `batch_planner.py:_is_test_path`)
- `globs_intersect(a, b)` — returns globs from `a` that share matching paths with any glob in `b`, after stripping test-path globs from both sides. Uses anchor-based probes for `dir/**` patterns and fnmatch for wildcards.
- `find_blocking_items(candidate_paths, in_flight)` — returns `(item_id, conflicting_globs)` tuples for in-flight items that block the candidate.

### 2. `orch/daemon/batch_manager.py` — Launch-time gate
- `_collect_in_flight_scopes(db)` — new method (lines 288–313) that queries `BatchItem` with status `{setting_up, executing, merging}` joined with `WorkItem`, filtering by `project_id` and `WorkItem.type != Research`.
- Gate inserted in `_process_batch()` (lines 390–429): before calling `_launch_item()`, checks for scope overlap against `in_flight_scopes`. Held items emit `item_held_for_scope` `DaemonEvent` and remain `pending` (no parallelism slot consumed). After launching, appends the item's scope to `in_flight_scopes` so same-group items in the same poll cycle see each other.

### 3. `orch/daemon/merge_queue.py` — `merge_info["conflict_files"]` capture
- `_CONFLICT_MARKER_RE` compiled at module level (line 50)
- In the success path (lines 262–270): parses the marker from stdout and stores `conflict_files` in `merge_info`
- In the error path (lines 329–337): parses stdout+stderr for the marker even when `MergeError` is raised

### 4. `executor/worktree_commit.sh` — `CONFLICT_FILES` marker
- Lines 286–305: After auto-resolving rebase conflicts, emits `[worktree_commit] CONFLICT_FILES <json_array>` to stdout
- Uses `jq` if available, falls back to a hand-rolled JSON encoder
- Marker is emitted before `git rebase --continue`, so it appears in stdout even when the continue fails

### 5. Tests
- `tests/unit/daemon/test_scope_overlap.py` — 26 tests: `is_test_path` (15 cases), `globs_intersect` (10 cases), `find_blocking_items` (5 cases)
- `tests/integration/daemon/test_batch_manager_scope_gate.py` — 8 tests covering: overlapping Features held, Research bypass, merged/setup_failed not in-flight, held item resumes, same-group mutual overlap
- `tests/integration/daemon/test_merge_info_conflict_files.py` — 4 tests covering: auto-resolved conflict, clean rebase, rebase failure with marker, multiple conflicts

## Test Results

```
48 passed, 1 warning
```

All unit and integration tests pass cleanly.

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/scope_overlap.py` | **CREATED** — pure glob-intersection helpers |
| `orch/daemon/batch_manager.py` | Modified — `_collect_in_flight_scopes()` + scope gate in `_process_batch()` |
| `orch/daemon/merge_queue.py` | Modified — `conflict_files` capture in success and error paths |
| `executor/worktree_commit.sh` | Modified — `CONFLICT_FILES` marker emission in rebase block |
| `tests/unit/daemon/test_scope_overlap.py` | **CREATED** — 26 unit tests |
| `tests/integration/daemon/test_batch_manager_scope_gate.py` | **CREATED** — 8 integration tests |
| `tests/integration/daemon/test_merge_info_conflict_files.py` | **CREATED** — 4 integration tests |

## Quality Checks

| Check | Result |
|-------|--------|
| `make format` | ✅ ok |
| `make typecheck` | ✅ ok |
| `make lint` | ✅ ok (shellcheck errors on worktree_commit.sh are pre-existing, not from my changes) |
| Unit tests | ✅ 36 passed |
| Integration tests | ✅ 12 passed |

## Notes

- The `test_merge_info_conflict_files.py` tests mock `run_post_merge_apply` and `run_rollback` to prevent migration pipeline code from connecting to the live DB during tests. This was necessary because `_merge_item()` calls these functions unconditionally after the squash-merge.
- The `worktree_commit.sh` CONFLICT_FILES marker uses a JSON array on a single line: `[worktree_commit] CONFLICT_FILES ["file1","file2"]`. The regex `_CONFLICT_MARKER_RE` captures the JSON array portion.
- The `scope_overlap.py` sibling-path logic (`_same_parent`) considers two items in the same directory as blocking each other, even with different exact file paths — this is intentional per the F-00076 design notes.