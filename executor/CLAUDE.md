# executor/ — Bash Executor Scripts

Shell scripts that manage git worktrees and LLM agent execution. Called by the daemon.

## Critical Rules

- **NEVER** run `docker`, `docker compose`, or `docker-compose` from executor bash scripts. Executor scripts run as part of agent workflows and inherit the R1 rule from `docs/IW_AI_Core_Agent_Constraints.md`.

## Scripts

| Script | Purpose |
|--------|---------|
| `worktree_setup.sh` | Creates a git worktree for a work item branch; sets up environment |
| `step_executor.sh` | Launches an LLM agent (opencode or claude-code) inside the worktree |
| `step_executor_lib.sh` | Shared shell functions sourced by `step_executor.sh` |
| `worktree_commit.sh` | Squash-merges completed worktree back to main and removes the worktree |

## Usage Pattern

The daemon calls these scripts in sequence for each work item:

1. `worktree_setup.sh <project_path> <branch_name>` — creates worktree
2. `step_executor.sh <worktree_path> <step_type> <agent_type>` — runs agent, writes PID
3. `worktree_commit.sh <project_path> <branch_name>` — merges on success

## Gotchas

- Scripts read `IW_CORE_*` env vars from the daemon's environment — do **NOT** hardcode paths
- `step_executor.sh` writes the agent PID to a file the daemon monitors for heartbeat/stall detection
- `worktree_commit.sh` performs a `--squash` merge — all work-item commits become a single merge commit on main
- Worktrees live under `.worktrees/<item-id>/` in the project root (not in `iw-ai-core/`)
