# Step 09: Executor Scripts (Bash)

## Context

The daemon is complete and calls bash scripts for worktree management and step execution. Now port these scripts from InnoForge and adapt them for iw-ai-core.

Read these documents:
- `IW_AI_Core_Daemon_Design.md` — section 4.3 (item launch, worktree setup), 4.4 (step launch)
- `IW_AI_Core_Migration_Checklist.md` — section 4.5 (executor scripts changes)

Source files in InnoForge to reference:
- `/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/scripts/worktree_setup.sh`
- `/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/scripts/step_executor.sh`
- `/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/scripts/step_executor_lib.sh`
- `/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/scripts/worktree_commit.sh`

## Task

### 1. `executor/worktree_setup.sh`

Port from InnoForge's `scripts/worktree_setup.sh` with these changes:
- Add `project_repo_root` as a parameter (not hardcoded to InnoForge path)
- Sync skills from iw-ai-core: `iw sync-skills --project <project_id>` (or copy from `$IW_CORE_ROOT/skills/`)
- Remove any manifest file writes — state goes through `iw` CLI only
- Keep: git worktree creation, venv setup, npm install, branch creation
- Live step state is read by the agent at runtime via `iw item-status --json`; no static brief file is generated

**Script signature:**
```bash
executor/worktree_setup.sh <item_id> <project_repo_root> [<iw_core_root>]
```

### 2. `executor/step_executor.sh`

Port from InnoForge's `scripts/step_executor.sh` with these changes:
- Add `project_repo_root` parameter
- Replace all manifest file reads/writes with `iw` CLI calls:
  - `set_step_status` → `iw step-done` or `iw step-fail`
  - `get_step_status` → `iw item-status --json` and parse
- Remove manifest file dependency entirely — DB is the only state
- Keep: agent launch logic, timeout handling (now reads timeout from step_run via `iw`), log capture

### 3. `executor/step_executor_lib.sh`

Port shared functions from InnoForge's `scripts/step_executor_lib.sh`:
- Keep: verdict parsing, log formatting, helper functions
- Remove: all functions that read/write manifest JSON files
- Replace with: functions that call `iw` CLI

### 4. `executor/worktree_commit.sh`

Port from InnoForge's `scripts/worktree_commit.sh`:
- Add `project_repo_root` parameter
- Keep: squash-merge logic, conflict detection, branch cleanup
- This script is mostly unchanged — it's pure git operations

### 5. Manual Testing

These are bash scripts — test them manually, not via pytest:
- [ ] `worktree_setup.sh I001 /path/to/project` creates worktree with correct structure
- [ ] Skills are synced into the worktree's `.claude/skills/`
- [ ] `worktree_commit.sh I001 /path/to/project` squash-merges to main
- [ ] Scripts work when the iw-ai-core daemon is running

## Acceptance Criteria

- [ ] All scripts accept `project_repo_root` parameter (no hardcoded paths)
- [ ] No script reads or writes manifest JSON files — all state through `iw` CLI
- [ ] Worktree creation, step execution, and merge all work end-to-end
- [ ] Scripts are executable (`chmod +x`)
