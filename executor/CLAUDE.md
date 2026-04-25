# executor/ — Bash Executor Scripts

Shell scripts that manage git worktrees and LLM agent execution. Called by the daemon.

## Critical Rules

- **NEVER** run `docker`, `docker compose`, or `docker-compose` from executor bash scripts. Executor scripts run as part of agent workflows and inherit the R1 rule from `docs/IW_AI_Core_Agent_Constraints.md`.
- **NEVER** invoke `alembic` from executor scripts. Migrations are daemon-driven — agents generate migration files, the daemon applies them. Executor scripts must not call `alembic upgrade` / `alembic downgrade` directly. See `docs/IW_AI_Core_Agent_Constraints.md`.

## Scripts

| Script | Purpose |
|--------|---------|
| `worktree_setup.sh` | Creates a git worktree for a work item branch; sets up environment |
| `step_executor.sh` | Launches an LLM agent (opencode or claude-code) inside the worktree |
| `step_executor_lib.sh` | Shared shell functions sourced by `step_executor.sh` |
| `worktree_commit.sh` | Squash-merges completed worktree back to main and removes the worktree |
| `scope_gate.py` | Stdin-driven scope enforcer invoked by `worktree_commit.sh` Step 2.25 — blocks merges that touch files outside the manifest's `scope.allowed_paths` |

## Usage Pattern

The daemon calls these scripts in sequence for each work item:

1. `worktree_setup.sh <project_path> <branch_name>` — creates worktree
2. `step_executor.sh <worktree_path> <step_type> <agent_type>` — runs agent, writes PID
3. `worktree_commit.sh <project_path> <branch_name>` — merges on success

## Gotchas

- Scripts read `IW_CORE_*` env vars from the daemon's environment — do **NOT** hardcode paths
- `step_executor.sh` writes the agent PID to a file the daemon monitors for heartbeat/stall detection
- `worktree_commit.sh` performs a `--squash` merge — all work-item commits become a single merge commit on main
- `worktree_commit.sh` Step 2.25 runs the scope gate: if the item's `workflow-manifest.json` declares `scope.allowed_paths`, any modified file outside that allow-list (plus the implicit `ai-dev/active/<ID>/**` and `ai-dev/archive/<ID>/**`) blocks the merge. Legacy items without `scope` pass through — the gate is additive. Introduced after the 2026-04-22 I-00034 retrospective: QV fix-cycles had silently expanded scope by "fixing" pre-existing failures in unrelated files.
- Worktrees live under `.worktrees/<item-id>/` in the project root (not in `iw-ai-core/`)
- `browser_verification` steps do **not** use these scripts — their lifecycle (docker compose for the project-under-test, Playwright harness) lives in `orch/daemon/browser_env.py`, opted into per-project via `.iw-orch.json`

## Compose Lifecycle Ownership

Executor scripts MUST NOT call docker. The per-worktree compose stack
introduced in F-00062 is owned by `orch/daemon/worktree_compose.py` —
the daemon invokes `up()` after `worktree_setup.sh` returns and `down()`
on terminal-status transitions. See [`docs/IW_AI_Core_Worktree_Isolation.md`](docs/IW_AI_Core_Worktree_Isolation.md).
