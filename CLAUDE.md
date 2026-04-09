# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# IW AI Core — Platform Context for AI Agents

## What This Repo Is

**IW AI Core** is a standalone AI orchestration platform that manages AI-assisted software development workflows across multiple projects. It replaces file-based tracking (markdown ID files, JSON manifests) inside InnoForge with a database-backed, multi-project system.

The repo lives at `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/` (main clone) and `/home/sergiog/dev/iw-doc-plan/development/iw-ai-core/` (dev clone).

**Key responsibility**: This platform orchestrates LLM agents running `iw step-start` / `iw step-done` / `iw step-fail` inside project worktrees. It is not a project itself — it is infrastructure for all projects.

---

## Architecture in One Paragraph

A single **daemon** polls PostgreSQL every 60 seconds, picks up approved batches across all registered projects, creates git worktrees, launches LLM agents (opencode or claude-code), monitors their progress via PID + heartbeat, handles fix cycles triggered by code reviews, and squash-merges completed items to main. A **FastAPI dashboard** (port 9900) provides real-time visibility and manual controls. The **`iw` CLI** is the agent-to-DB bridge: agents call `iw step-done` to record results. All operational state lives in PostgreSQL — no files, no race conditions.

---

## Repository Structure

```
iw-ai-core/
├── orch/                    # Core Python package
│   ├── config.py            # load_config() / get_db_url() — reads .env
│   ├── db/
│   │   ├── models.py        # All 10 SQLAlchemy 2.0 ORM models + FTS SQL constants
│   │   ├── session.py       # engine, SessionLocal, get_session() context manager
│   │   └── migrations/      # Alembic — env.py + versions/
│   ├── cli/                 # iw CLI (Click) — agent-to-DB bridge
│   ├── daemon/              # Orchestration daemon (polling loop)
│   ├── archive/             # Two-tier archive system (DB + zstd)
│   └── skills/              # Skill sync engine
├── dashboard/               # FastAPI web UI (Jinja2 + htmx + Tailwind CDN)
├── executor/                # Bash scripts: worktree_setup, step_executor, worktree_commit
├── skills/                  # Master skill copies (synced to each project)
├── templates/               # Default workflow templates
├── tests/
│   ├── unit/                # Fast, no I/O (config, state machine, logic)
│   └── integration/         # testcontainers PostgreSQL (models, DB behavior)
├── alembic.ini              # Alembic config — script_location = orch/db/migrations
├── pyproject.toml           # uv project: deps, ruff, mypy, pytest config
├── Makefile                 # make test-unit | test-integration | quality | db-migrate
├── docker-compose.yml       # Postgres container (reads .env)
└── projects.toml            # Project registry (daemon re-reads on SIGHUP)
```

---

## Database

**Engine**: PostgreSQL 15+ on port 5433 (configured in `.env`).

**10 tables** (all using `project_id` for multi-project isolation):

| Table | Purpose | PK |
|-------|---------|-----|
| `projects` | Registry of managed projects | `id` (TEXT) |
| `id_sequences` | Atomic sequential ID allocation | `(project_id, prefix)` |
| `work_items` | Features, Issues, ChangeRequests | `(project_id, id)` |
| `workflow_steps` | Step pipeline per work item | SERIAL |
| `step_runs` | Execution attempts (append-only) | SERIAL |
| `fix_cycles` | Review-triggered retry loops (append-only) | SERIAL |
| `batches` | Groups for parallel execution | `(project_id, id)` |
| `batch_items` | Work item ↔ batch mapping | SERIAL |
| `migration_locks` | Exclusive lock for Alembic migration creation | `project_id` |
| `daemon_events` | Audit trail (append-only) | SERIAL |

**ENUMs** (10 total): `work_item_type`, `work_item_status`, `work_item_phase`, `step_type`, `step_status`, `run_status`, `fix_trigger`, `fix_status`, `batch_status`, `batch_item_status`.

**FTS**: `work_items.design_doc_search` (TSVECTOR) is auto-updated by trigger `trg_work_items_fts` whenever `title` or `design_doc_content` changes.

**Note**: `DaemonEvent.metadata` column is named `event_metadata` in Python — SQLAlchemy reserves `metadata` on `DeclarativeBase` subclasses. The DB column is still called `metadata`.

### Live DB Setup

Port 5433 is occupied by a pre-existing `postgres` Docker container (not managed by docker-compose). The `iw_orch` user and database were manually created in it. If `make db-up` fails with "port already allocated", the DB is already running — just use `make db-migrate`.

To create the DB manually:
```bash
docker exec postgres psql -U postgres -c "CREATE USER iw_orch WITH PASSWORD 'iw_orch_dev';"
docker exec postgres psql -U postgres -c "CREATE DATABASE iw_orch OWNER iw_orch;"
```

---

## Technology Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Python | 3.12+ | `tomllib` in stdlib |
| ORM | SQLAlchemy 2.0 sync | `Mapped[]` declarative style |
| Driver | psycopg v3 (`psycopg[binary]`) | NOT psycopg2 |
| Migrations | Alembic 1.13+ | `alembic upgrade head` |
| Config | python-dotenv | loads `.env` at import time in `orch/config.py` |
| CLI | Click 8.1+ | entry point: `iw` |
| Dashboard | FastAPI + Jinja2 + htmx + Tailwind CDN | No build step |
| Archive | zstandard (zstd) | `.tar.zst` format |
| Package manager | uv | `uv sync`, `uv run` |
| Linter/formatter | Ruff | `line-length = 100` |
| Type checker | mypy strict | `plugins = ["sqlalchemy.ext.mypy.plugin"]` |
| Tests | pytest + testcontainers | containers on random ports |

---

## Configuration

All configuration lives in `.env` (gitignored). Never hardcode ports, URLs, or credentials.

Key env vars:
- `IW_CORE_DB_HOST`, `IW_CORE_DB_PORT` (5433), `IW_CORE_DB_NAME`, `IW_CORE_DB_USER`, `IW_CORE_DB_PASSWORD`
- `IW_CORE_DASHBOARD_PORT` (9900)
- `IW_CORE_POLL_INTERVAL` (60s), `IW_CORE_STALL_THRESHOLD` (600s)

`orch/config.py` calls `load_dotenv()` at module import. `load_config()` fails fast with `RuntimeError` if any required var is missing — no silent fallbacks.

---

## CLI Command Groups

The `iw` CLI (`orch/cli/main.py`) is composed of command modules registered as Click groups:

| Module | Commands |
|--------|----------|
| `id_commands.py` | `next-id`, `current-project` |
| `project_commands.py` | `register`, `projects list` |
| `item_commands.py` | `approve`, `item-status` |
| `step_commands.py` | `step-start`, `step-done`, `step-fail` |
| `batch_commands.py` | `batch-create`, `batch-approve`, `batch-status`, `batch-pause`, `batch-resume` |
| `lock_commands.py` | `migration-lock` |
| `search_commands.py` | `search` |
| `skills_commands.py` | `skills sync`, `init-project` |
| `daemon_commands.py` | `daemon start`, `daemon stop`, `daemon status` |

`orch/cli/utils.py` holds shared helpers (session access, output formatting).

---

## Testing Rules (NON-NEGOTIABLE)

1. **NEVER** connect tests to the live database (port 5433)
2. **ALL** DB tests use `testcontainers` (random Docker port)
3. **NEVER** call `importlib.reload(orch.config)` in tests — it re-runs `load_dotenv()` which restores deleted env vars from `.env`. Use `monkeypatch.delenv()` only.
4. After `Base.metadata.create_all()` in tests, execute `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (exported from `orch.db.models`) — the trigger is raw DDL not captured by `create_all()`.
5. testcontainers returns `psycopg2` URLs — always replace with `psycopg`: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`
6. **NEVER** mock the database in integration tests — use real testcontainers (FOR UPDATE locking can't be tested otherwise)

### Running Tests

```bash
make test-unit                              # Fast, no containers
make test-integration                       # Starts PostgreSQL testcontainer (~3s)
make quality                                # ruff check + ruff format --check + mypy
make check                                  # quality + all tests

# Run a single test file or test by name:
uv run pytest tests/unit/test_config.py -v
uv run pytest tests/integration/test_models.py -v
uv run pytest -k "test_next_id" -v         # Match by test name
```

---

## Implementation Progress

All 16 implementation steps are complete. See `docs/implementation/00_INDEX.md` for the plan.

Phases implemented: Foundation (01-02), CLI (03-05), Daemon (06-08), Executor scripts (09), Archive & Skills (10-11), Dashboard (12-15), Integration (16).

---

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| ORM mode | Sync SQLAlchemy | Daemon is a single-threaded polling loop |
| DB is source of truth | PostgreSQL only | No markdown files, no race conditions |
| Composite PKs | `(project_id, id)` for work items + batches | Multi-project isolation |
| Append-only tables | `step_runs`, `fix_cycles`, `daemon_events` | Full audit trail |
| Two-tier content storage | Tier 1 (DB TEXT), Tier 2 (zstd archive) | Always-viewable summaries + compact artifacts |
| No hardcoded values | Everything in `.env` | Multiple instances, no test interference |
| Test isolation | testcontainers on random ports | Tests run alongside live platform |

---

## Common Commands

```bash
uv run iw --help              # CLI help
uv run alembic upgrade head   # Apply migrations
uv run alembic revision --autogenerate -m "MSG"  # Generate migration
make db-migrate               # Same as alembic upgrade head
make daemon-start             # Start orchestration daemon
make dashboard-start          # Start web dashboard on port 9900
```

---

## Playwright CLI (Browser Automation)

This project runs on headless WSL/Linux with no display server. Browser automation uses `playwright-cli` exclusively.

### Setup

- **Binary**: `~/.local/bin/playwright-cli` (pre-installed globally)
- **Browser cache**: `~/.cache/ms-playwright/` (Chromium pre-cached)
- **Project config**: `.playwright/cli.config.json` — tells playwright-cli to use bundled Chromium
- **Permission**: `Bash(playwright-cli:*)` in `.claude/settings.local.json`

### Rules (NON-NEGOTIABLE)

1. **ALWAYS** use `playwright-cli` for all browser interaction
2. **ALWAYS** run `playwright-cli kill-all` before starting a new browser session
3. **NEVER** use `agent-browser` — it attempts to install its own Chromium and fails in headless environments
4. **NEVER** run `npx playwright install`, `agent-browser install --with-deps`, or similar browser install commands
5. **NEVER** write Playwright scripts that call `chromium.launch()` directly
6. **NEVER** modify `.playwright/cli.config.json` from LLM code

### Common Commands

```bash
playwright-cli --version             # Verify installation
playwright-cli kill-all              # Kill all sessions (run before starting)
playwright-cli open <url>            # Open a URL in browser
playwright-cli goto <url>            # Navigate current page
playwright-cli snapshot              # Get accessibility snapshot of current page
playwright-cli screenshot            # Take screenshot
playwright-cli click <selector>      # Click an element
playwright-cli fill <selector> <val> # Fill a form field
playwright-cli eval <js>             # Execute JavaScript
playwright-cli tab-list              # List open tabs
playwright-cli tab-new <url>         # Open new tab
playwright-cli console               # Get console messages
playwright-cli network               # Get network requests
playwright-cli close-all             # Close all browsers
playwright-cli list                  # List active sessions
```

### Session Management

Use `-s=<name>` flag for named sessions (useful for auth persistence):
```bash
playwright-cli open -s=dashboard http://localhost:9900
playwright-cli snapshot -s=dashboard
playwright-cli close-all -s=dashboard
```

---

## Docs Reference

| Document | What It Contains |
|----------|-----------------|
| `docs/IW_AI_Core_Database_Schema.md` | Complete DDL, ENUMs, state machines, trigger code |
| `docs/IW_AI_Core_Tech_Stack.md` | All technology choices, test fixtures, Makefile, docker-compose |
| `docs/IW_AI_Core_Architecture.md` | System layout, end-to-end flow, component responsibilities |
| `docs/IW_AI_Core_CLI_Spec.md` | Every `iw` command: inputs, outputs, DB operations |
| `docs/IW_AI_Core_Daemon_Design.md` | Daemon loop, state transitions, monitoring logic |
| `docs/IW_AI_Core_Dashboard_Design.md` | Dashboard pages, htmx patterns, SSE |
| `docs/implementation/00_INDEX.md` | 16-step implementation plan with dependencies |
