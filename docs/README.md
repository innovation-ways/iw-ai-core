# IW AI Core — Planning & Documentation

This folder contains all planning, architecture, and reference documents for the **IW AI Core** project — the standalone multi-project AI orchestration platform.

## Documents

| Document | Description |
|----------|-------------|
| [IW_AI_Core_Architecture.md](IW_AI_Core_Architecture.md) | **Architecture.** Complete architecture, end-to-end flows, multi-project management, two-tier storage, database schema, skills distribution, migration plan. |
| [IW_AI_Core_Architecture.pdf](IW_AI_Core_Architecture.pdf) | Branded Innovation Ways PDF rendering of the architecture document. |
| [IW_AI_Core_Requirements.md](IW_AI_Core_Requirements.md) | **Requirements.** Functional requirements by component, non-functional requirements, constraints, phasing, acceptance criteria. |
| [IW_AI_Core_Tech_Stack.md](IW_AI_Core_Tech_Stack.md) | **Technology Stack.** Libraries, versions, licenses, testing strategy with full isolation, project structure, Makefile, configuration. |
| [IW_AI_Core_Database_Schema.md](IW_AI_Core_Database_Schema.md) | **Database Schema.** Complete SQL DDL, state machines, event catalog, seed data. Basis for Alembic initial migration. |
| [IW_AI_Core_CLI_Spec.md](IW_AI_Core_CLI_Spec.md) | **CLI Specification.** All `iw` commands, flags, output formats (human + JSON), exit codes, examples, caller matrix. |
| [IW_AI_Core_Daemon_Design.md](IW_AI_Core_Daemon_Design.md) | **Daemon Design.** Main loop, batch processing, step monitoring, merge queue, crash recovery, graceful shutdown, action handlers. |
| [IW_AI_Core_Dashboard_Design.md](IW_AI_Core_Dashboard_Design.md) | **Dashboard Design.** Theme (Discord/shadcn), page wireframes, htmx patterns, SSE real-time updates, component library, API routes. |
| [IW_AI_Core_Migration_Checklist.md](IW_AI_Core_Migration_Checklist.md) | **Migration Checklist.** Step-by-step cutover from InnoForge, file inventory, verification tests, rollback plan. |

## Implementation Prompts

Sequential, copy-paste-ready prompts for AI agents. See [implementation/00_INDEX.md](implementation/00_INDEX.md) for the full execution order and dependency graph.

| # | Prompt | Module |
|---|--------|--------|
| 01 | [Project Setup](implementation/01_foundation/01_project_setup.md) | Repo skeleton, pyproject.toml, .env, Makefile, docker-compose |
| 02 | [Config & DB](implementation/01_foundation/02_config_and_db.md) | Config loading, SQLAlchemy models, Alembic migration |
| 03 | [CLI Core](implementation/02_cli/03_cli_core.md) | next-id, register, approve, current-project |
| 04 | [CLI Steps & Batches](implementation/02_cli/04_cli_steps_and_batches.md) | step-start/done/fail, batch-create/approve/status |
| 05 | [CLI Remaining](implementation/02_cli/05_cli_remaining.md) | migration-lock, archive, search, daemon, projects |
| 06 | [Daemon Core](implementation/03_daemon/06_state_machine_and_core.md) | State machine, main loop, signals, project registry |
| 07 | [Step Monitor](implementation/03_daemon/07_step_monitor.md) | PID health, timeout, stall, zombie detection |
| 08 | [Batch Manager](implementation/03_daemon/08_batch_manager_and_merge.md) | Batch processing, item/step launch, merge queue |
| 09 | [Executor Scripts](implementation/04_executor/09_executor_scripts.md) | Port worktree_setup.sh, step_executor.sh, worktree_commit.sh |
| 10 | [Archive System](implementation/05_archive/10_archive_system.md) | Tier 1 (DB) + Tier 2 (zstd), on-demand extraction |
| 11 | [Skill Sync](implementation/06_skills/11_skill_sync.md) | Sync engine, init-project, lock file |
| 12 | [Dashboard Foundation](implementation/07_dashboard/12_dashboard_foundation.md) | FastAPI app, theme, base template, components |
| 13 | [Running & Actions](implementation/07_dashboard/13_running_and_actions.md) | Running tasks, kill/restart/skip, SSE, toasts |
| 14 | [Project Pages](implementation/07_dashboard/14_project_pages.md) | Dashboard, batches, batch detail, item detail |
| 15 | [Queue, History, System](implementation/07_dashboard/15_queue_history_system.md) | Queue, history, search, system status |
| 16 | [Register & Verify](implementation/08_integration/16_register_and_verify.md) | Register InnoForge, end-to-end verification |

## Diagrams

All diagrams are in `diagrams/` as `.drawio` files (open with [draw.io](https://app.diagrams.net)):

| Diagram | Description |
|---------|-------------|
| [01_system_architecture.drawio](diagrams/01_system_architecture.drawio) | Platform overview — all components and connections |
| [02_end_to_end_flow.drawio](diagrams/02_end_to_end_flow.drawio) | Complete journey: `/iw-new-incident` to merged code (5 phases) |
| [03_multi_project_topology.drawio](diagrams/03_multi_project_topology.drawio) | How 3 project repos connect to 1 centralized backend |
| [04_data_flow.drawio](diagrams/04_data_flow.drawio) | State vs Content split, two-tier storage model |
| [05_skills_distribution.drawio](diagrams/05_skills_distribution.drawio) | Package-like skill management and distribution |
| [06_database_schema.drawio](diagrams/06_database_schema.drawio) | Full ER diagram for the `iw_orch` PostgreSQL database |

## Reference Documents (Prior Design Work)

Historical design documents that informed the architecture:

| Document | Description |
|----------|-------------|
| [01_original_detailed_design.md](reference/01_original_detailed_design.md) | Original Phase 2 detailed design (2026-03-31) |
| [02_dashboard_enhancement.md](reference/02_dashboard_enhancement.md) | Dashboard & orchestration enhancements E1-E9 |
| [03_merge_fix_automation.md](reference/03_merge_fix_automation.md) | Post-merge quality & AI fix automation |
