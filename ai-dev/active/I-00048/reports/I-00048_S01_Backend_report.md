# I-00048 S01 Backend Report

## What was done

Added Step 7 to `executor/worktree_setup.sh` that copies the work item context directory (`ai-dev/active/<ID>/`) into the worktree after creation, and writes per-worktree git exclude patterns so the copied files are never staged by `git add -A`.

## Files changed

- `executor/worktree_setup.sh` — added Step 7 (lines ~197–215)

## Key implementation details

- `cp -r` copies the entire `ai-dev/active/<ID>/` tree into the worktree
- If source does not exist (manually registered items), the step skips silently
- `git -C "$WORKTREE_DIR" rev-parse --git-dir` resolves the worktree-specific gitdir (may be relative, e.g. `../.git/worktrees/<name>`); resolved to absolute before use
- Patterns appended to `$WORKTREE_GITDIR/info/exclude` (per-worktree, not shared with main repo or other worktrees):
  - `ai-dev/active/<ID>/prompts/`
  - `ai-dev/active/<ID>/workflow-manifest.json`
  - `ai-dev/active/<ID>/*.md`
- `reports/` is intentionally NOT excluded — agent-written reports must still be committed
- Final `echo "$WORKTREE_DIR"` line remains last on stdout

## Preflight results

| Gate | Result |
|------|--------|
| format | ok (445 files already formatted) |
| typecheck | ok (0 errors in 191 source files) |
| lint | ok (All checks passed) |

## Test results

- `make test-unit`: 1908 passed, 2 failed, 2 skipped
- The 2 failures (`test_apply_refuses_in_agent_context`, `test_rollback_refuses_in_agent_context`) are pre-existing and unrelated to this change (confirmed by stashing changes and re-running)

## Blockers

None.