# iw-ai-core

**AI orchestration platform for AI-assisted software development.**

IW AI Core runs AI coding agents across one or more registered projects. A single daemon picks approved batches of work items, launches LLM agents (opencode or claude-code) inside isolated git worktrees, drives fix cycles when reviews fail, and squash-merges the result back to `main`. A FastAPI dashboard on port 9900 gives humans a place to design, approve, watch, and review everything — plus tools for code understanding, documentation, and quality gates.

All operational state lives in PostgreSQL (port 5433). No markdown files, no race conditions.

---

## What you can do with it

Once a project is registered, the web UI exposes:

| View | What it offers |
|------|---------------|
| **Queue / History / Batches** | Design work items (features, incidents, change requests), group them into batches, approve, pause, resume, restart — watch them run in real time |
| **Code** | Browse modules auto-extracted from an architecture map, read AI-generated Level 2 module docs, explain individual symbols, and ask free-form questions. Answers stream with inline citations (file paths, symbols, work-item IDs) |
| **Docs** | Per-project documentation catalogue: create, version, HTML/PDF export, section-level diffs, stale detection against source files, AI regeneration via background jobs, and editorial guidelines per doc type / instance / section. `/docs` (global) searches across all projects |
| **Research** | Curated library of research documents (market, tech, deep-dive) with status and editorial-category filters |
| **Tests / Quality** | Launch project-configured test suites and static-analysis gates from the browser; view live logs and Allure reports; kill runaway runs |
| **Jobs** | Unified feed of every background job: batches, code indexing, doc generation, research drafts — one filter, one status model |
| **Worktrees** | Git status of every active agent worktree, one-click commit or prune |
| **Daemon** | Start/stop/restart the orchestration daemon from the UI |

Behind all of this: a polling daemon (60s default), a sync-SQLAlchemy ORM over PostgreSQL, a Click-based `iw` CLI that agents use to report progress, and a small bash executor that manages git worktrees.

---

## Quick start

```bash
# First-time setup
./ai-core.sh install      # uv sync + start DB + run migrations

# Normal operation
./ai-core.sh start        # db → migrate → daemon → dashboard
./ai-core.sh status       # service status + DB identity + recent daemon events
./ai-core.sh stop

# Open http://localhost:9900
```

`./ai-core.sh` with no arguments drops you into an interactive menu.

### Database

The orchestration DB runs on port 5433 and is **NOT** managed by the default `docker-compose.yml` (which is intentionally empty to prevent accidental `docker compose up` from creating a rogue empty volume that clobbers production data — the 2026-04-22 incident).

See [`docs/IW_AI_Core_DB_Setup.md`](docs/IW_AI_Core_DB_Setup.md) for the two supported setup paths (production bind-mount vs. dev bootstrap). Always go through `./ai-core.sh db start`; never invoke `docker compose` directly against the orchestration DB.

### Configuration

Copy `.env.example` → `.env` and adjust. Key variables:

- `IW_CORE_DB_HOST`, `IW_CORE_DB_PORT` (5433), `IW_CORE_DB_NAME`, `IW_CORE_DB_USER`, `IW_CORE_DB_PASSWORD`
- `IW_CORE_DASHBOARD_PORT` (9900)
- `IW_CORE_POLL_INTERVAL`, `IW_CORE_STALL_THRESHOLD`
- `IW_CORE_EXPECTED_INSTANCE_ID` — pins the DB identity fingerprint (CR-00014) so the daemon refuses to start against the wrong database

Registered projects live in `projects.toml`. After editing it, `./ai-core.sh daemon reload` sends SIGHUP and the daemon re-syncs.

---

## Architecture at a glance

```
┌──────────────┐        ┌────────────────────────┐
│   Agents     │  iw    │   PostgreSQL (5433)    │
│ (opencode /  │<──────>│   single source of     │
│  claude-code)│        │   truth — 19 tables    │
└──────┬───────┘        └──────────┬─────────────┘
       │  launched in                 ▲
       │  git worktree                │ poll / FOR UPDATE
       ▼                              │
┌──────────────┐        ┌────────────────────────┐
│  Executor    │<───────│        Daemon          │
│  (bash)      │ launch │  batches · merges      │
└──────────────┘        │  doc-jobs · code-index │
                        └──────────┬─────────────┘
                                   │
                        ┌────────────────────────┐
                        │  FastAPI Dashboard     │
                        │  htmx · SSE · Tailwind │
                        └────────────────────────┘
```

- **`orch/`** — models, CLI, daemon, RAG, jobs aggregator, doc services
- **`dashboard/`** — routers + Jinja2/htmx UI (22 routers grouped by concern)
- **`executor/`** — bash scripts for worktree setup/commit and step launch
- **`tests/`** — unit, integration (testcontainers), and dashboard (TestClient) suites
- **`skills/`, `commands/`, `agents/`** — master copies synced to each managed project
- **`doc-system/`** — editorial config (brand, catalog, guidelines) used by doc-generator skills

See [`CLAUDE.md`](CLAUDE.md) for platform-level rules and navigation, then the per-directory `CLAUDE.md` files under `orch/`, `dashboard/`, `executor/`, `tests/`, and `orch/rag/`.

---

## Common commands

```bash
uv run iw --help                                    # CLI help — agents use this
uv run iw db-identity check                         # verify DB fingerprint
make test-unit                                      # fast tests, no containers
make test-integration                               # PostgreSQL testcontainer
make quality                                        # ruff + format-check + mypy
make check                                          # quality + all tests
make db-migrate                                     # alembic upgrade head
uv run alembic revision --autogenerate -m "MSG"     # generate a migration
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [`CLAUDE.md`](CLAUDE.md) | Platform-level context, critical rules, common commands |
| [`docs/IW_AI_Core_Architecture.md`](docs/IW_AI_Core_Architecture.md) | System layout, end-to-end flows |
| [`docs/IW_AI_Core_Database_Schema.md`](docs/IW_AI_Core_Database_Schema.md) | DDL, ENUMs, state machines, triggers |
| [`docs/IW_AI_Core_Daemon_Design.md`](docs/IW_AI_Core_Daemon_Design.md) | Daemon loop, batch processing, monitoring |
| [`docs/IW_AI_Core_Dashboard_Design.md`](docs/IW_AI_Core_Dashboard_Design.md) | Dashboard pages, htmx patterns, SSE |
| [`docs/IW_AI_Core_CLI_Spec.md`](docs/IW_AI_Core_CLI_Spec.md) | Every `iw` command |
| [`docs/IW_AI_Core_DB_Setup.md`](docs/IW_AI_Core_DB_Setup.md) | DB setup paths + 2026-04-22 incident |
| [`docs/IW_AI_Core_Agent_Constraints.md`](docs/IW_AI_Core_Agent_Constraints.md) | What agents and automation must never do |
| [`docs/implementation/00_INDEX.md`](docs/implementation/00_INDEX.md) | Implementation plan index |
