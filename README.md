# iw-ai-core

AI orchestration platform managing AI-assisted development workflows across multiple projects.

## Overview

Single **daemon** polls PostgreSQL (port 5433) every 60s, picks approved batches across registered projects, creates git worktrees, launches LLM agents (opencode or claude-code), handles fix cycles, and squash-merges to main. **FastAPI dashboard** (port 9900) provides real-time visibility. **`iw` CLI** is the agent-to-DB bridge — agents call `iw step-done` to record results. All operational state lives in PostgreSQL — no files, no race conditions.

## Database

The orchestration DB runs on port 5433 and is NOT managed by the default
`docker-compose.yml`. See [`docs/IW_AI_Core_DB_Setup.md`](docs/IW_AI_Core_DB_Setup.md)
for the two supported setup paths (production bind-mount vs. dev bootstrap)
and the 2026-04-22 incident that shaped this split.

For routine ops, use `./ai-core.sh` — the script knows which compose file
to invoke and will no-op cleanly if the DB is already running.

## Quick Start

```bash
./ai-core.sh install   # uv sync + db start + migrate
./ai-core.sh start     # db → migrate → daemon → dashboard
./ai-core.sh status    # full status summary
```

## Architecture

- **Daemon** (`orch/daemon/`) — polling loop, batch processing, step monitoring, merge queue
- **CLI** (`orch/cli/`) — `iw` command suite for agents and operators
- **Dashboard** (`dashboard/`) — FastAPI + htmx web UI
- **Database** (`orch/db/`) — SQLAlchemy models + Alembic migrations

See [`CLAUDE.md`](CLAUDE.md) for full architecture details and critical rules.

## Documentation

| Document | Description |
|----------|-------------|
| [`CLAUDE.md`](CLAUDE.md) | Platform-level AI context, critical rules, common commands |
| [`docs/IW_AI_Core_DB_Setup.md`](docs/IW_AI_Core_DB_Setup.md) | DB setup (two paths) and the 2026-04-22 incident |
| [`docs/IW_AI_Core_Architecture.md`](docs/IW_AI_Core_Architecture.md) | System layout, end-to-end flows |
| [`docs/IW_AI_Core_Database_Schema.md`](docs/IW_AI_Core_Database_Schema.md) | DDL, ENUMs, state machines, triggers |
| [`docs/IW_AI_Core_Daemon_Design.md`](docs/IW_AI_Core_Daemon_Design.md) | Daemon loop, batch processing, monitoring |
| [`docs/IW_AI_Core_CLI_Spec.md`](docs/IW_AI_Core_CLI_Spec.md) | Every `iw` command |
| [`docs/implementation/00_INDEX.md`](docs/implementation/00_INDEX.md) | 16-step implementation plan |
