# Step 01: Project Setup

## Context

You are building IW AI Core — a standalone multi-project AI orchestration platform. This is the first step: creating the repository skeleton, configuration files, and development tooling.

Read these documents for full context:
- `IW_AI_Core_Tech_Stack.md` — section 5 (Project Structure), section 6 (Makefile), section 7 (Dependencies), section 8 (Docker Compose & Environment)

## Task

Create the complete project skeleton for iw-ai-core. This is a Python project using uv for package management.

### 1. `pyproject.toml`

Create with:
- Project name: `iw-ai-core`
- Python >= 3.12
- Runtime dependencies: sqlalchemy, psycopg[binary], alembic, click, rich, fastapi, uvicorn[standard], jinja2, python-multipart, zstandard, python-dotenv
- Dev dependencies: pytest, pytest-cov, testcontainers[postgres], factory-boy, freezegun, ruff, mypy, pre-commit, types-freezegun
- Entry point: `iw = "orch.cli.main:cli"`
- Ruff config: target-version="py312", line-length=100, select all recommended rules, allow assert in tests
- mypy config: strict=true, python_version="3.12"
- pytest config: testpaths=["tests"], asyncio not needed (sync SQLAlchemy)

### 2. `.env.example`

All configuration variables with documented defaults. See Tech Stack doc section 8.1. Include: DB host/port/name/user/password, dashboard host/port, daemon poll interval/stall threshold/PID file, archive dir/TTL, log level/file.

### 3. `.gitignore`

Include: .env, .venv/, __pycache__/, *.pyc, archive/, logs/, .daemon.pid, *.egg-info/, dist/, .mypy_cache/, .ruff_cache/, .pytest_cache/, htmlcov/

### 4. `docker-compose.yml`

PostgreSQL 15-alpine container reading ALL values from `.env` (no hardcoded ports or credentials). See Tech Stack doc section 8.2.

### 5. `Makefile`

Targets: install, lint, format, typecheck, quality, test-unit, test-integration, test, check, db-up, db-down, db-migrate, db-revision, daemon-start, daemon-stop, dashboard-start. See Tech Stack doc section 6.

### 6. Directory structure

Create all empty `__init__.py` files and directories:
- `orch/`, `orch/cli/`, `orch/daemon/`, `orch/db/`, `orch/db/migrations/`, `orch/archive/`, `orch/skills/`
- `executor/`
- `dashboard/`, `dashboard/routers/`, `dashboard/templates/`, `dashboard/templates/components/`, `dashboard/templates/pages/`, `dashboard/templates/fragments/`, `dashboard/static/`
- `skills/`, `templates/`
- `archive/` (with `.gitkeep`)
- `logs/` (with `.gitkeep`)
- `tests/`, `tests/unit/`, `tests/integration/`, `tests/fixtures/`
- `tests/conftest.py` (empty for now)
- `tests/integration/conftest.py` (empty for now)

### 7. `.pre-commit-config.yaml`

Hooks for ruff (lint + format) and mypy.

### 8. `projects.toml`

Empty project registry:
```toml
# IW AI Core — Project Registry
# Add projects here. Daemon re-reads on SIGHUP or file change.
```

## Acceptance Criteria

- [ ] `cp .env.example .env` works
- [ ] `uv sync` installs all dependencies without errors
- [ ] `uv run ruff check .` passes (no source files to lint yet, should exit 0)
- [ ] `uv run mypy orch/` passes (empty packages)
- [ ] `docker compose up -d` starts PostgreSQL on the port from `.env`
- [ ] `docker compose down` stops cleanly
- [ ] `uv run pytest` exits 0 (no tests yet)
- [ ] `make check` runs quality + test without errors
