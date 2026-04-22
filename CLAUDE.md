# IW AI Core — CLAUDE.md

AI orchestration platform managing AI-assisted development workflows across multiple projects.

## Quick Navigation

| Task | Location |
|------|----------|
| ORM models & schema | `orch/db/models.py` · `docs/IW_AI_Core_Database_Schema.md` |
| iw CLI commands | `orch/cli/` · see `orch/CLAUDE.md` |
| Daemon logic | `orch/daemon/` · `docs/IW_AI_Core_Daemon_Design.md` |
| Dashboard routes/templates | `dashboard/` · see `dashboard/CLAUDE.md` |
| Executor bash scripts | `executor/` · see `executor/CLAUDE.md` |
| Test patterns & rules | `tests/conftest.py` · see `tests/CLAUDE.md` |
| Configuration | `orch/config.py` (reads `.env`) |
| Migrations | `orch/db/migrations/versions/` |
| Skills master copies | `skills/` (synced to each project via `iw skills sync`) |

## Architecture

Single **daemon** polls PostgreSQL (port 5433) every 60s, picks approved batches across registered projects, creates git worktrees, launches LLM agents (opencode or claude-code), handles fix cycles, and squash-merges to main. **FastAPI dashboard** (port 9900) provides real-time visibility. **`iw` CLI** is the agent-to-DB bridge — agents call `iw step-done` to record results. All operational state lives in PostgreSQL — no files, no race conditions.

## Critical Rules

- **NEVER** connect tests to live DB (port 5433) — use testcontainers only (see `tests/CLAUDE.md`)
- **NEVER** call `importlib.reload(orch.config)` in tests — use `monkeypatch.delenv()` instead
- **NEVER** mock the database in integration tests — FOR UPDATE locking can't be tested otherwise
- **MUST** replace psycopg2 URLs in testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests
- **CRITICAL**: `DaemonEvent.metadata` is named `event_metadata` in Python — SQLAlchemy reserves `metadata`
- **NEVER** use `agent-browser` for browser automation — use `playwright-cli` exclusively
- **NEVER** run `npx playwright install` or modify `.playwright/cli.config.json`
- **NEVER** run `docker kill`, `docker stop`, `docker rm`, `docker restart`, `docker compose up|down|restart`, `docker-compose up|down|restart`, `docker volume rm|prune`, or `docker system|container|image prune` — these can clobber shared infrastructure (see 2026-04-22 incident). Full policy: `docs/IW_AI_Core_Agent_Constraints.md`. Exceptions: read-only `docker ps|inspect|logs`, testcontainers via pytest, and `./ai-core.sh` / `make` targets.

## Configuration

All config in `.env` (gitignored). **NEVER** hardcode ports, URLs, or credentials.  
Key vars: `IW_CORE_DB_HOST`, `IW_CORE_DB_PORT` (5433), `IW_CORE_DB_NAME`, `IW_CORE_DB_USER`, `IW_CORE_DB_PASSWORD`, `IW_CORE_DASHBOARD_PORT` (9900), `IW_CORE_POLL_INTERVAL`, `IW_CORE_STALL_THRESHOLD`.

## Live DB Setup

Port 5433: pre-existing `postgres` Docker container (not docker-compose managed). If `make db-up` fails with "port already allocated", the DB is already running — skip to `make db-migrate`.

## Common Commands

```bash
uv run iw --help                                    # CLI help
make test-unit                                      # Fast tests (no containers)
make test-integration                               # Tests with PostgreSQL testcontainer
make lint                                           # ruff + node --check on dashboard/static/**/*.js
make quality                                        # lint (ruff + JS syntax) + format-check + mypy
make check                                          # quality + all tests
make db-migrate                                     # alembic upgrade head
make daemon-start                                   # Start orchestration daemon
make dashboard-start                                # Start web dashboard (port 9900)
uv run alembic revision --autogenerate -m "MSG"     # Generate migration
```

## Playwright CLI (Browser Automation)

Headless WSL/Linux — use `playwright-cli` exclusively. Binary: `~/.local/bin/playwright-cli`. Config: `.playwright/cli.config.json`.

**ALWAYS** run `playwright-cli kill-all` before starting a new browser session.  
**NEVER** call `chromium.launch()` directly, use `agent-browser`, or run install commands.

```bash
playwright-cli kill-all              # Kill all sessions first
playwright-cli open <url>            # Open URL in browser
playwright-cli snapshot              # Accessibility snapshot of current page
playwright-cli screenshot            # Take screenshot
playwright-cli click <selector>      # Click an element
playwright-cli fill <selector> <v>   # Fill a form field
playwright-cli -s=<name> open <url>  # Named session (for auth persistence)
```

## Docs Reference

| Document | What It Contains |
|----------|-----------------|
| `docs/IW_AI_Core_Database_Schema.md` | DDL, ENUMs, state machines, trigger code |
| `docs/IW_AI_Core_Tech_Stack.md` | Technology choices, test fixtures, Makefile |
| `docs/IW_AI_Core_Architecture.md` | System layout, end-to-end flow |
| `docs/IW_AI_Core_CLI_Spec.md` | Every `iw` command: inputs, outputs, DB ops |
| `docs/IW_AI_Core_Daemon_Design.md` | Daemon loop, state transitions, monitoring |
| `docs/IW_AI_Core_Dashboard_Design.md` | Dashboard pages, htmx patterns, SSE |
| `docs/implementation/00_INDEX.md` | 16-step implementation plan |
