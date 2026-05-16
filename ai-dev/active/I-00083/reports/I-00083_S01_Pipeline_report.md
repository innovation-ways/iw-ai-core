# I-00083 S01 Pipeline Report

## What Was Done

Implemented two complementary changes to address branch-base drift across in-flight items:

### Change 1: Narrow the `iw approve` chore commit (Requirement 1)

**File**: `orch/active_files.py`

Changed `ensure_active_files_committed` to stage only allow-listed paths instead of the full `ai-dev/active/<item_id>/` directory:

- `<ID>_*_Design.md` — technical design documents
- `<ID>_Functional.md` — human-facing summary
- `workflow-manifest.json` — step definitions
- `prompts/` — all step prompt files

Added a prominently commented `_CHORE_COMMIT_PATHSPECS` allow-list with a clear explanation of what is excluded and why, citing I-00083 to deter future regressions.

**Logic**: The `git status --porcelain` check still inspects the full directory (to detect when nothing needs committing at all), but the `git add` now uses the narrow pathspec list. If only non-design files are dirty, the function returns early without committing.

### Change 2: Launch-time sibling-scope check (Requirement 2)

**File**: `orch/daemon/batch_manager.py`

Added three new private methods to `BatchManager`:

- `_list_worktree_files(worktree_path)` — runs `git ls-tree -r --name-only HEAD` to enumerate all tracked files in the new worktree's HEAD tree.
- `_glob_matches_any(glob_pattern, file_paths)` — matches a gitignore-style glob against a set of file paths using `PurePath.match()` with an `fnmatch` fallback.
- `_collect_in_flight_sibling_items(db, current_item_id)` — queries WorkItems with active BatchItem statuses (`setting_up`, `executing`, `merging`) for the same project, excluding the item being launched.
- `_emit_sibling_drift_log(db, item_id, worktree_path)` — orchestrates the check and emits the structured INFO log line.

The call site is in `_launch_item`, immediately after `_setup_worktree` returns successfully and `worktree_path` is set.

**v1 approximation**: A sibling contributes to `sibling_paths_without_merge` when `merge_commit_sha IS NULL` (not yet merged) AND its `impacted_paths` globs match at least one file in the new worktree's HEAD tree.

**Log line format** (emitted exactly once per worktree-create):
```
worktree create: item=<ID> base=<sha> in_flight_siblings=[<sib1>,...] sibling_paths_without_merge=<N> details=[<sib1>:<count>,...]
```

When `sibling_paths_without_merge > 0`, an additional WARNING line is emitted to make the drift visible in ops dashboards.

**Behavior**: WARN only — worktree creation is never blocked.

## Files Changed

| File | Change |
|------|--------|
| `orch/active_files.py` | Rewrote to use narrow allow-list for chore commit staging |
| `orch/daemon/batch_manager.py` | Added `_list_worktree_files`, `_glob_matches_any`, `_collect_in_flight_sibling_items`, `_emit_sibling_drift_log`; added call site in `_launch_item` |
| `tests/integration/test_branch_base_drift.py` | Created AC1 RED→GREEN reproduction test |

## Test Results

**RED state** (pre-fix): Test failed with:
```
AssertionError: Expected INFO log line with 'worktree create:' and
'sibling_paths_without_merge' but none found.
```

**GREEN state** (post-fix): `1 passed, 0 failed` in 4.13s.

## Quality Gates

- `make format`: 710 files already formatted (no changes needed)
- `make type-check`: Success — no issues found in 249 source files
- `make lint`: All checks passed

## Decision Notes

Chose option (b) from the design doc (narrow chore commit) plus the launch-time sibling-scope check, as specified in the "Implementation options — DECIDED" section. No fatal flaws were encountered during implementation.

The `active_files.py` rewrite required handling the edge case where only non-design files are dirty (in which case there is nothing to commit via the chore path, and the function returns early without running `git add`).

## Backwards Compatibility

- Items already approved with the old chore-commit shape continue to work — no history is rewritten.
- The fix only affects items approved or worktrees created after this change lands.
- Solo-item runs emit `in_flight_siblings=[] sibling_paths_without_merge=0` and are otherwise identical to today's behavior.
