# IW AI Core — Implementation Plan

## Execution Order

Each step below is a self-contained prompt file. Execute them in order — each step depends on the previous ones being complete.

**Convention**: Give the prompt file content to an AI agent (Claude Code, OpenCode, etc.) inside the iw-ai-core repo. The agent reads the referenced design docs and implements + tests the module.

**TDD rule**: Every prompt instructs the agent to write tests FIRST, then implement. No exceptions.

---

### Phase 1: Foundation

| # | File | Module | Depends On | Est. Effort |
|---|------|--------|-----------|-------------|
| 01 | [01_foundation/01_project_setup.md](01_foundation/01_project_setup.md) | Repo skeleton, pyproject.toml, .env, Makefile, docker-compose | Nothing | Small |
| 02 | [01_foundation/02_config_and_db.md](01_foundation/02_config_and_db.md) | Config loading, SQLAlchemy models, Alembic migration, session factory | #01 | Medium |

### Phase 2: CLI

| # | File | Module | Depends On | Est. Effort |
|---|------|--------|-----------|-------------|
| 03 | [02_cli/03_cli_core.md](02_cli/03_cli_core.md) | Click entry point, `next-id`, `current-project`, `register`, `approve` | #02 | Medium |
| 04 | [02_cli/04_cli_steps_and_batches.md](02_cli/04_cli_steps_and_batches.md) | `step-start/done/fail`, `batch-create/approve/status/pause/resume` | #03 | Medium |
| 05 | [02_cli/05_cli_remaining.md](02_cli/05_cli_remaining.md) | `migration-lock`, `archive`, `search`, `item-status`, `daemon start/stop/status`, `projects list` | #04 | Medium |

### Phase 3: Daemon

| # | File | Module | Depends On | Est. Effort |
|---|------|--------|-----------|-------------|
| 06 | [03_daemon/06_state_machine_and_core.md](03_daemon/06_state_machine_and_core.md) | State machine, daemon main loop, signal handlers, startup/shutdown, project registry | #05 | Large |
| 07 | [03_daemon/07_step_monitor.md](03_daemon/07_step_monitor.md) | PID health check, timeout detection, stall detection, zombie cleanup | #06 | Medium |
| 08 | [03_daemon/08_batch_manager_and_merge.md](03_daemon/08_batch_manager_and_merge.md) | Batch processing, item launch, step launch, merge queue | #07 | Large |

### Phase 4: Executor Scripts

| # | File | Module | Depends On | Est. Effort |
|---|------|--------|-----------|-------------|
| 09 | [04_executor/09_executor_scripts.md](04_executor/09_executor_scripts.md) | Port worktree_setup.sh, step_executor.sh, worktree_commit.sh | #08 | Medium |

### Phase 5: Archive & Skills

| # | File | Module | Depends On | Est. Effort |
|---|------|--------|-----------|-------------|
| 10 | [05_archive/10_archive_system.md](05_archive/10_archive_system.md) | Tier 1 (DB content) + Tier 2 (zstd compress), on-demand extraction | #05 | Medium |
| 11 | [06_skills/11_skill_sync.md](06_skills/11_skill_sync.md) | Skill sync engine, init-project, lock file management | #05 | Medium |

### Phase 6: Dashboard

| # | File | Module | Depends On | Est. Effort |
|---|------|--------|-----------|-------------|
| 12 | [07_dashboard/12_dashboard_foundation.md](07_dashboard/12_dashboard_foundation.md) | FastAPI app, theme CSS, base template, Jinja2 components, project selector | #05 | Medium |
| 13 | [07_dashboard/13_running_and_actions.md](07_dashboard/13_running_and_actions.md) | Running tasks page, kill/restart/skip/restart-from endpoints, SSE | #12 | Large |
| 14 | [07_dashboard/14_project_pages.md](07_dashboard/14_project_pages.md) | Project dashboard, batch list, batch detail, work item detail with tabs | #13 | Large |
| 15 | [07_dashboard/15_queue_history_system.md](07_dashboard/15_queue_history_system.md) | Queue & backlog, history with search, system status page | #14 | Medium |

### Phase 7: Integration

| # | File | Module | Depends On | Est. Effort |
|---|------|--------|-----------|-------------|
| 16 | [08_integration/16_register_and_verify.md](08_integration/16_register_and_verify.md) | Register InnoForge, end-to-end verification, fix any integration issues | #15 | Medium |

---

## Parallelization Opportunities

Steps 10 (archive) and 11 (skills) can run in parallel — they don't depend on each other.

Steps 12-15 (dashboard) are sequential, but steps 10-11 can run in parallel with step 12.

```
01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09
                          ↓              ↓
                         10 ─────────────┼──→ 16
                         11 ─────────────┤
                         12 → 13 → 14 → 15 ─┘
```

## Total: 16 implementation steps
