# IW AI Core — Technology Stack & Testing Strategy

**Project**: IW AI Core (Innovation Ways AI Orchestration Platform)
**Author**: Sergio G. + Claude
**Date**: 2026-04-07
**Version**: 1.0.0
**Status**: Draft

---

## 1. Overview

This document specifies the exact technologies, libraries, and tooling for IW AI Core. Every choice is justified against the functional requirements defined in `IW_AI_Core_Requirements.md` and constrained by the decisions in `IW_AI_Core_Architecture.md`.

**Governing constraints:**
- Permissive OSS only (MIT, BSD, Apache-2.0) — no AGPL, no proprietary
- Single developer, single machine — no over-engineering for scale
- No SPA build pipeline — server-rendered dashboard
- Python for daemon + CLI, Bash for executor scripts
- PostgreSQL for all state

---

## 2. Runtime Stack

### 2.1. Python

| Item | Choice | Version | License |
|------|--------|---------|---------|
| Runtime | CPython | 3.12+ | PSF |

**Why 3.12+**: Performance improvements (PEP 684 per-interpreter GIL), better error messages, `tomllib` in stdlib (for `projects.toml`). Same version as InnoForge — consistent tooling.

### 2.2. Database

| Item | Choice | Version | License | Port |
|------|--------|---------|---------|------|
| Database | PostgreSQL | 15+ | PostgreSQL | `.env` |
| Driver | psycopg (v3) | 3.1+ | LGPL-3.0 | — |
| ORM | SQLAlchemy | 2.0+ (sync) | MIT | — |
| Migrations | Alembic | 1.13+ | MIT | — |
| Migration model | Agent writes file, daemon applies (R2 policy) | — | — |

**Migration model** (R2): Agents generate migration files only. The daemon's
merge pipeline applies them in three phases:

```
Phase 1 (pre-merge):   dry-run against fresh testcontainer
                       → fail: MIGRATION_INVALID, fix-cycle triggered
Phase 2 (post-merge):  apply to live DB (port 5433)
                       → fail: auto-rollback attempted
Phase 3 (rollback):    if Phase 2 rollback fails → merge queue frozen
```

Agents MUST NOT run `alembic upgrade head` against the live DB. See
[`docs/IW_AI_Core_Agent_Constraints.md`](docs/IW_AI_Core_Agent_Constraints.md) (R2).
| Env loading | python-dotenv | 1.0+ | BSD-3 | — |

**Why sync SQLAlchemy**: The daemon is a single-threaded polling loop. Async adds complexity (event loop management, async session scoping) for zero benefit. The CLI is also synchronous — call, get result, exit.

**Why psycopg v3 over psycopg2**: Pure Python mode available (no C compilation needed), better typing support, connection pooling built-in. LGPL-3.0 is permissive enough for application use (not embedding).

**Port assignment**: All ports are configurable via `.env`. Default suggestion is 5433 for DB and 9900 for dashboard, but nothing is hardcoded.

### 2.3. Docker Compose — Bootstrap Only

The default `docker-compose.yml` at the project root is intentionally empty.
The `db` service lives in `docker-compose.bootstrap.yml` and requires an
explicit `-f` flag. This split exists because the old default compose file
caused a data-loss incident on 2026-04-22 — running `docker compose up` from
a git worktree created a per-worktree empty volume that clobbered the
production DB on port 5433 for ~80 minutes.

**Production path**: raw `docker run` with host bind mount at `/opt/postgres/data`.
See [`docs/IW_AI_Core_DB_Setup.md`](docs/IW_AI_Core_DB_Setup.md).

**Dev bootstrap path**: `docker compose -f docker-compose.bootstrap.yml up -d db`
using named volume `iw-ai-core_pgdata`. Clearly marked as dev-only —
do not use for the long-lived orchestration DB.

### 2.4. Dashboard

| Item | Choice | Version | License |
|------|--------|---------|---------|
| Web framework | FastAPI | 0.115+ | MIT |
| Templating | Jinja2 | 3.1+ | BSD-3 |
| Interactivity | htmx | 2.0+ | BSD-2 |
| Styling | Tailwind CSS (CDN) | 3.4+ | MIT |
| Real-time | SSE (native FastAPI) | — | — |
| Charts | Chart.js (CDN) | 4.4+ | MIT |
| ASGI server | Uvicorn | 0.30+ | BSD-3 |

**Why FastAPI**: Async routing for SSE streams, automatic OpenAPI docs (useful for the action endpoints), dependency injection, proven in InnoForge. Note: the daemon is sync, but the dashboard is async (it serves HTTP requests concurrently).

**Why Tailwind CSS via CDN**: No build step. The Play CDN (`<script src="https://cdn.tailwindcss.com">`) works for development and internal tools. A standalone Tailwind CLI binary exists for compiling a static stylesheet, but it is not reliable inside agent worktrees today — see "Tailwind CLI fallback strategy" below. Clean utility classes, consistent styling, responsive out of the box.

**Why Chart.js via CDN**: Lightweight, no npm, good enough for analytics charts. Loaded only on analytics pages.

**Why not the current custom CSS from InnoForge dashboard**: Starting fresh with Tailwind gives a cleaner foundation. The current dashboard CSS evolved organically — Tailwind provides consistency from day one.

### Tailwind CLI fallback strategy

Agent worktrees sometimes have incomplete `node_modules`, which causes the Tailwind CLI to fail with missing modules — notably `postcss-selector-parser`, as seen in I-00067. The `make css` target is declared in `.PHONY` in the Makefile with no rule body, so it exits with `Nothing to be done for 'css'` without attempting compilation.

When new styling is required and the Tailwind CLI cannot run, append plain CSS rules directly to `dashboard/static/styles.css`. The dashboard serves this file as-is, so plain CSS rules take effect without any compilation step. The Tailwind utility classes already on the page continue to come from the CDN.

Do not use this fallback when the Tailwind CLI is known-good in your environment and `make css` actually produces output. Today, neither is guaranteed in agent worktrees. A future change may give the `css` target a real rule body or remove it from `.PHONY`; until then, this subsection is the authoritative guidance.

### 2.4. Compression

| Item | Choice | Version | License |
|------|--------|---------|---------|
| Archive compression | python-zstandard | 0.23+ | BSD-3 |
| Archive format | tar + zstd | — | — |

**Why Zstandard**: 3-5x faster decompression than gzip, better compression ratio, configurable compression levels. A typical work item (200 KB) compresses to ~40 KB and decompresses in <50ms. Python bindings via `python-zstandard` (BSD-3).

### 2.5. CLI

| Item | Choice | Version | License |
|------|--------|---------|---------|
| CLI framework | Click | 8.1+ | BSD-3 |
| Output formatting | Rich | 13.0+ | MIT |

**Why Click**: Battle-tested, clean decorator-based API, automatic `--help`, command groups, parameter validation. Used by hundreds of major projects (Flask, pip, etc.).

**Why Rich**: Pretty terminal output for `iw batch-status`, `iw search`, progress bars for `iw sync-skills`. Optional — all commands also support `--json` for machine-readable output.

### 2.6. Process Management

| Item | Choice | Notes |
|------|--------|-------|
| Daemon process control | stdlib `subprocess`, `os.kill`, `signal` | No external process manager needed |
| PID file | stdlib `pathlib` | Single-instance enforcement |
| Worktree/agent launch | `subprocess.Popen` | Captures PID, command, log file |

No external dependencies for process management. The daemon uses stdlib for everything: `subprocess.Popen` to launch agents, `os.kill(pid, 0)` to check alive, `signal.SIGTERM` to kill.

---

## 3. Development & Quality Stack

### 3.1. Package Management

| Item | Choice | Version | License |
|------|--------|---------|---------|
| Package manager | uv | 0.5+ | MIT |
| Project metadata | pyproject.toml | PEP 621 | — |
| Lock file | uv.lock | — | — |

**Why uv**: 10-100x faster than pip, built-in venv management, deterministic lock file. Same developer experience as InnoForge's migration path.

### 3.2. Code Quality

| Item | Choice | Config |
|------|--------|--------|
| Linter + Formatter | Ruff | `pyproject.toml` `[tool.ruff]` |
| Type checker | mypy (strict) | `pyproject.toml` `[tool.mypy]` |
| Pre-commit hooks | pre-commit | `.pre-commit-config.yaml` |

**Ruff config baseline:**
```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "DTZ", "T20", "ICN", "PIE", "PT", "RSE", "RET", "SLF", "SIM", "TCH", "ARG", "PTH", "ERA"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # assert allowed in tests
```

**mypy config baseline:**
```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
```

### 3.3. Testing Stack

| Item | Choice | Version | License |
|------|--------|---------|---------|
| Test framework | pytest | 8.0+ | MIT |
| Test containers | testcontainers[postgres] | 4.0+ | Apache-2.0 |
| Fixtures/factories | Factory Boy | 3.3+ | MIT |
| Coverage | pytest-cov | 5.0+ | MIT |
| Time control | freezegun | 1.4+ | Apache-2.0 |

---

## 4. Testing Strategy

### 4.1. Core Principle: Total Isolation

**Tests MUST NEVER touch the platform's running database, daemon, or any running process.**

Every test session gets its own PostgreSQL instance via `testcontainers`. No shared ports. No shared state. Tests can run in parallel with the live platform, with InnoForge's tests, or with each other — without interference.

```
Live platform:
  PostgreSQL on port 5433   <-- NEVER touched by tests
  Daemon PID running        <-- NEVER touched by tests
  Dashboard on port 9900    <-- NEVER touched by tests

Test session A:
  PostgreSQL testcontainer on random port 54321 (assigned by Docker)
  No daemon, no dashboard

Test session B (can run simultaneously):
  PostgreSQL testcontainer on random port 54387 (different container)
  No daemon, no dashboard

InnoForge tests (can also run simultaneously):
  PostgreSQL testcontainer on random port 54412 (InnoForge's own)
```

### 4.2. Test Isolation Rules (NON-NEGOTIABLE)

1. **NEVER** hardcode database URLs, ports, or credentials in test code
2. **NEVER** add fallback URLs pointing to localhost:5433 or the platform database
3. **NEVER** connect to the live PostgreSQL from tests under any circumstances
4. **ALL** database connection strings in tests MUST come from testcontainers
5. **NEVER** send signals to real PIDs from tests — use mocks for process management
6. **NEVER** create real git worktrees from tests — use temp directories
7. **NEVER** modify real project repos from tests — use isolated fixtures
8. **Tests MUST** be runnable while the platform is actively executing batches
9. **Tests MUST** be runnable in parallel (multiple `pytest` processes simultaneously)

### 4.3. Test Structure

```
tests/
├── conftest.py                    # Shared fixtures (DB session factory, etc.)
├── unit/                          # Fast, no I/O, no containers
│   ├── test_cli_commands.py       # iw CLI command logic
│   ├── test_state_machine.py      # Status transition validation
│   ├── test_daemon_logic.py       # Timeout, stall, zombie detection
│   ├── test_batch_planner.py      # Dependency analysis, group assignment
│   ├── test_project_registry.py   # Project discovery, config validation
│   ├── test_archive.py            # Compression, extraction, cleanup
│   ├── test_skill_sync.py         # Version comparison, override detection
│   └── test_workflow_parser.py    # workflow.md parsing and step generation
├── integration/                   # Real PostgreSQL via testcontainers
│   ├── conftest.py                # Testcontainer setup, session factory
│   ├── test_id_allocation.py      # Atomic ID allocation under concurrency
│   ├── test_work_items.py         # CRUD, status transitions, archival
│   ├── test_step_runs.py          # Step execution recording, PID tracking
│   ├── test_batches.py            # Batch lifecycle, merge ordering
│   ├── test_search.py             # Full-text search queries
│   ├── test_migration_lock.py     # Concurrent lock acquisition
│   └── test_dashboard_api.py      # Dashboard API endpoints against real DB
└── fixtures/
    ├── factories.py               # Factory Boy factories for all models
    ├── sample_workflow.md          # Test workflow definition
    └── sample_design_doc.md       # Test design document content
```

### 4.4. Database Test Fixtures (testcontainers)

```python
# tests/integration/conftest.py

import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orch.db.models import Base


@pytest.fixture(scope="session")
def pg_container():
    """Start a PostgreSQL container for the entire test session.

    The container runs on a random port assigned by Docker.
    It is completely isolated from the platform DB on port 5433.
    """
    with PostgresContainer("postgres:15") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_engine(pg_container):
    """Create a SQLAlchemy engine connected to the test container."""
    engine = create_engine(pg_container.get_connection_url())
    # Create all tables (no Alembic in tests — direct metadata create)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Provide a transactional DB session that rolls back after each test.

    Each test gets a clean slate without needing to truncate tables.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

**Key design choices:**
- **Session-scoped container**: One PostgreSQL container per `pytest` run. Starting a container takes ~2 seconds; reusing it across all tests avoids the overhead.
- **Per-test transaction rollback**: Each test runs inside a transaction that is rolled back after the test completes. This gives each test a clean database without the cost of table truncation or container restart.
- **Random port**: `testcontainers` assigns a random available port. No hardcoded ports means no collisions with anything.

### 4.5. What to Test and Where

| Component | Unit Tests | Integration Tests | Why |
|-----------|-----------|------------------|-----|
| **`iw` CLI commands** | Input validation, flag parsing, error messages | Command execution against real DB | CLI is the primary user interface — bugs here break the workflow |
| **State machine** | All valid/invalid transitions | — | Pure logic, no I/O needed |
| **Daemon: timeout detection** | Time calculations, threshold logic | — | Pure logic with freezegun for time control |
| **Daemon: zombie detection** | PID alive/dead logic (mocked os.kill) | — | Can't send real signals in tests |
| **Daemon: stall detection** | Heartbeat age calculations | — | Pure logic |
| **Daemon: batch processing** | Execution group ordering, parallelism limits | Batch lifecycle with DB state | Complex interaction between DB state and logic |
| **Batch planner** | Dependency graph analysis, group assignment | — | Pure algorithm |
| **ID allocation** | — | Concurrent allocation (threading) | MUST test real DB locking behavior |
| **Archive** | Tar/zstd compression/extraction (temp dirs) | DB content storage + file cleanup | Both: file operations + DB content |
| **Skill sync** | Version comparison, override detection | — | Pure logic |
| **Workflow parser** | Parse workflow.md, generate step pipeline | — | Pure parsing |
| **Dashboard API** | — | Endpoint responses against real DB | Needs real data to verify queries |
| **Search** | — | FTS queries against real DB with sample data | PostgreSQL-specific behavior |
| **Migration lock** | — | Concurrent lock acquisition (threading) | MUST test real DB row locking |

### 4.6. What NOT to Test

- **Dashboard HTML rendering**: Jinja2 templates produce HTML — visual spot-checking is sufficient for an internal tool. No Playwright/browser tests.
- **htmx interactions**: These are declarative HTML attributes. If the endpoint returns the right HTML, htmx does its job.
- **Executor bash scripts**: These are ported from InnoForge and proven in production. Test them manually during migration, not via automated tests.
- **LLM agent behavior**: The platform launches agents and records their results. What the agent does inside is not the platform's concern.
- **Git operations**: Worktree creation, merge, cleanup — these are bash scripts calling git. Test them manually, not via pytest.

### 4.7. Process Management Testing (Mocked)

Tests that involve PIDs, signals, and process lifecycle MUST mock `os.kill` and `subprocess.Popen`:

```python
# tests/unit/test_daemon_logic.py

from unittest.mock import patch, MagicMock
from freezegun import freeze_time
from datetime import datetime, timedelta

from orch.daemon import monitor_running_steps


def test_zombie_detection(db_session):
    """A step with a dead PID should be marked as failed."""
    # Arrange: step_run with status='running' and a PID
    run = create_step_run(db_session, status="running", pid=99999)

    # Act: PID is dead (ProcessLookupError on kill -0)
    with patch("os.kill", side_effect=ProcessLookupError):
        monitor_running_steps(db_session)

    # Assert
    assert run.status == "failed"
    assert "exited unexpectedly" in run.error_message


@freeze_time("2026-04-07 10:30:00")
def test_timeout_detection(db_session):
    """A step running longer than its timeout should be killed."""
    # Arrange: started 60 min ago, timeout is 45 min
    run = create_step_run(
        db_session,
        status="running",
        pid=12345,
        started_at=datetime(2026, 4, 7, 9, 30, 0),  # 60 min ago
        timeout_secs=2700,  # 45 min
    )

    # Act: PID is alive but over timeout
    with patch("os.kill") as mock_kill:
        mock_kill.side_effect = [None, None]  # kill -0 succeeds, then SIGTERM succeeds
        monitor_running_steps(db_session)

    # Assert: SIGTERM sent, marked as timeout
    assert run.status == "timeout"
    assert "Exceeded 2700s" in run.error_message
```

**Never** `os.kill` a real PID from tests. Always mock.

### 4.8. Concurrent ID Allocation Testing

This is the most critical integration test — it validates the `FOR UPDATE` lock under real concurrency:

```python
# tests/integration/test_id_allocation.py

import threading
from orch.cli.commands import next_id


def test_concurrent_id_allocation_no_duplicates(db_session_factory):
    """10 threads allocating IDs simultaneously must get unique results."""
    results = []
    errors = []

    def allocate():
        try:
            session = db_session_factory()
            result = next_id(session, project_id="test-project", prefix="I")
            results.append(result)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=allocate) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors during allocation: {errors}"
    assert len(results) == 10
    assert len(set(results)) == 10  # ALL unique — no duplicates
    # Verify sequential: I001, I002, ..., I010
    expected = {f"I{i:03d}" for i in range(1, 11)}
    assert set(results) == expected
```

This test MUST run against a real PostgreSQL (testcontainer) — mock databases don't implement `FOR UPDATE` locking.

---

## 5. Project Structure

```
iw-ai-core/
├── pyproject.toml               # Project metadata, dependencies, tool config
├── uv.lock                      # Deterministic dependency lock
├── Makefile                     # Developer commands
├── .env.example                 # All config vars documented (committed)
├── .env                         # Actual config values (NOT in git)
├── .pre-commit-config.yaml      # Pre-commit hooks
├── .gitignore                   # Includes .env, archive/, .venv/, etc.
├── docker-compose.yml           # PostgreSQL (reads from .env)
├── projects.toml                # Project registry
├── CLAUDE.md                    # Platform-level AI context
│
├── orch/                        # Python package — core platform
│   ├── __init__.py
│   ├── cli/                     # iw CLI (Click)
│   │   ├── __init__.py
│   │   ├── main.py              # Click group entry point
│   │   ├── id_commands.py       # next-id, current-project
│   │   ├── item_commands.py     # register, approve, archive
│   │   ├── step_commands.py     # step-start, step-done, step-fail
│   │   ├── batch_commands.py    # batch-create, batch-approve, batch-status
│   │   ├── skill_commands.py    # sync-skills, init-project
│   │   ├── lock_commands.py     # migration-lock acquire/release/status
│   │   ├── search_commands.py   # search
│   │   └── daemon_commands.py   # daemon start/stop/status
│   ├── daemon/                  # Orchestration daemon
│   │   ├── __init__.py
│   │   ├── main.py              # Entry point, main loop
│   │   ├── batch_manager.py     # Per-project batch processing
│   │   ├── step_monitor.py      # PID health, timeout, stall, zombie detection
│   │   ├── merge_queue.py       # Sequential merge per project
│   │   ├── state_machine.py     # Valid state transitions
│   │   ├── project_registry.py  # Project discovery, config loading
│   │   ├── quota_monitor.py     # LLM usage polling
│   │   └── git_status.py        # Per-project git state
│   ├── db/                      # Database layer
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy models (all tables)
│   │   ├── session.py           # Engine + session factory
│   │   └── migrations/          # Alembic
│   │       ├── env.py
│   │       └── versions/
│   ├── archive/                 # Two-tier archive system
│   │   ├── __init__.py
│   │   ├── archiver.py          # Tier 1 (DB) + Tier 2 (compress) logic
│   │   └── extractor.py         # On-demand extraction to tmp
│   └── skills/                  # Skill sync engine
│       ├── __init__.py
│       └── sync.py              # Version comparison, copy, lock file
│
├── executor/                    # Bash scripts (ported from InnoForge)
│   ├── step_executor.sh
│   ├── step_executor_lib.sh
│   ├── worktree_setup.sh
│   └── worktree_commit.sh
│
├── dashboard/                   # FastAPI web dashboard
│   ├── __init__.py
│   ├── app.py                   # FastAPI application factory
│   ├── dependencies.py          # DB session, project context
│   ├── routers/
│   │   ├── projects.py          # Project selector, overview
│   │   ├── batches.py           # Batch list, detail, actions
│   │   ├── items.py             # Work item detail, actions
│   │   ├── running.py           # Running tasks view
│   │   ├── history.py           # Completed items, search
│   │   ├── analytics.py         # Charts, metrics
│   │   ├── system.py            # Daemon status, quota, git
│   │   └── sse.py               # SSE notification stream
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html
│   │   ├── projects/
│   │   ├── batches/
│   │   ├── items/
│   │   ├── running/
│   │   └── system/
│   └── static/                  # Favicon, custom CSS overrides
│
├── skills/                      # Master skill copies
│   ├── iw-new-incident/
│   ├── iw-new-feature/
│   ├── iw-new-cr/
│   ├── iw-batch-execute/
│   ├── iw-workflow/
│   └── ...
│
├── templates/                   # Default workflow templates
│   ├── Feature_Design_Template.md
│   ├── Issue_Design_Template.md
│   └── ...
│
├── archive/                     # Compressed artifacts (NOT in git)
│   └── .gitkeep
│
└── tests/
    ├── conftest.py
    ├── unit/
    │   └── ...
    ├── integration/
    │   ├── conftest.py          # Testcontainer fixtures
    │   └── ...
    └── fixtures/
        └── ...
```

---

## 6. Makefile

```makefile
# ============================================================
# IW AI Core — Developer Commands
# ============================================================

.PHONY: install test test-unit test-integration quality check \
        lint format typecheck db-up db-down db-migrate \
        daemon-start daemon-stop dashboard-start

# --- Setup ---
install:
	uv sync
	uv run alembic upgrade head

# --- Quality ---
lint:
	uv run ruff check .

format:
	uv run ruff format --check .

typecheck:
	uv run mypy orch/ dashboard/

quality: lint format typecheck

# --- Tests ---
test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

test: test-unit test-integration

# --- All checks (run before commit) ---
check: quality test

# --- Database ---
db-up:
	docker compose -f docker-compose.bootstrap.yml up -d db

db-down:
	docker compose -f docker-compose.bootstrap.yml down

db-migrate:
	uv run alembic upgrade head

db-revision:
	uv run alembic revision --autogenerate -m "$(MSG)"

# --- Services ---
daemon-start:
	uv run python -m orch.daemon.main &

daemon-stop:
	uv run iw daemon stop

dashboard-start:
	uv run uvicorn dashboard.app:create_app --factory --host 0.0.0.0 --port 9900 --reload
```

---

## 7. Dependencies Summary

### 7.1. Runtime Dependencies

```toml
[project]
name = "iw-ai-core"
requires-python = ">=3.12"

dependencies = [
    # Database
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.1",
    "alembic>=1.13",

    # CLI
    "click>=8.1",
    "rich>=13.0",

    # Dashboard
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",

    # Archive
    "zstandard>=0.23",

    # Config
    "python-dotenv>=1.0",
    # tomllib is stdlib in 3.12+
]
```

### 7.2. Development Dependencies

```toml
[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "testcontainers[postgres]>=4.0",
    "factory-boy>=3.3",
    "freezegun>=1.4",

    # Quality
    "ruff>=0.8",
    "mypy>=1.13",
    "pre-commit>=4.0",

    # Type stubs
    "types-freezegun",
]
```

### 7.3. License Audit

| Package | License | Compliant |
|---------|---------|-----------|
| SQLAlchemy | MIT | Yes |
| psycopg | LGPL-3.0 | Yes (application use) |
| Alembic | MIT | Yes |
| Click | BSD-3 | Yes |
| Rich | MIT | Yes |
| FastAPI | MIT | Yes |
| Uvicorn | BSD-3 | Yes |
| Jinja2 | BSD-3 | Yes |
| zstandard | BSD-3 | Yes |
| python-dotenv | BSD-3 | Yes |
| pytest | MIT | Yes (dev only) |
| testcontainers | Apache-2.0 | Yes (dev only) |
| Factory Boy | MIT | Yes (dev only) |
| freezegun | Apache-2.0 | Yes (dev only) |
| Ruff | MIT | Yes (dev only) |
| mypy | MIT | Yes (dev only) |

**Zero AGPL or proprietary dependencies.** All permissive OSS.

---

## 8. Docker Compose & Environment Configuration

### 8.1. `.env.example` (committed to git)

```bash
# ============================================================
# IW AI Core — Environment Configuration
# ============================================================
# Copy this file to .env and adjust values for your environment.
# .env is in .gitignore — never committed.
# ============================================================

# --- Database ---
IW_CORE_DB_HOST=localhost
IW_CORE_DB_PORT=5433
IW_CORE_DB_NAME=iw_orch
IW_CORE_DB_USER=iw_orch
IW_CORE_DB_PASSWORD=iw_orch_dev

# Computed by the application from the above:
# IW_CORE_DB_URL=postgresql+psycopg://${IW_CORE_DB_USER}:${IW_CORE_DB_PASSWORD}@${IW_CORE_DB_HOST}:${IW_CORE_DB_PORT}/${IW_CORE_DB_NAME}

# --- Dashboard ---
IW_CORE_DASHBOARD_HOST=0.0.0.0
IW_CORE_DASHBOARD_PORT=9900

# --- Daemon ---
IW_CORE_POLL_INTERVAL=60
IW_CORE_STALL_THRESHOLD=600
IW_CORE_PID_FILE=.daemon.pid

# --- Archive ---
IW_CORE_ARCHIVE_DIR=./archive
IW_CORE_ARCHIVE_TTL=600

# --- Logging ---
IW_CORE_LOG_LEVEL=INFO
IW_CORE_LOG_FILE=./logs/daemon.log
```

### 8.2. `docker-compose.yml` (intentionally empty — historical)

> **Note**: The default `docker-compose.yml` is intentionally empty. The `db`
> service was moved to `docker-compose.bootstrap.yml` after the 2026-04-22
> incident. The snippet below is historical — it no longer reflects the actual
> file. See [docs/IW_AI_Core_DB_Setup.md](docs/IW_AI_Core_DB_Setup.md).

```yaml
# docker-compose.yml
# ALL values come from .env — nothing hardcoded.
services:
  db:
    image: postgres:15-alpine
    container_name: iw-ai-core-db
    ports:
      - "${IW_CORE_DB_PORT:-5433}:5432"
    environment:
      POSTGRES_DB: ${IW_CORE_DB_NAME:-iw_orch}
      POSTGRES_USER: ${IW_CORE_DB_USER:-iw_orch}
      POSTGRES_PASSWORD: ${IW_CORE_DB_PASSWORD:-iw_orch_dev}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${IW_CORE_DB_USER:-iw_orch}"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

For the current bootstrap compose file see
`docker-compose.bootstrap.yml`. For DB setup paths see
[docs/IW_AI_Core_DB_Setup.md](docs/IW_AI_Core_DB_Setup.md).

### 8.3. Application Configuration Loading

```python
# orch/config.py
from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env from the repo root
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_FILE)


def get_db_url() -> str:
    """Build database URL from individual env vars."""
    host = os.environ["IW_CORE_DB_HOST"]
    port = os.environ["IW_CORE_DB_PORT"]
    name = os.environ["IW_CORE_DB_NAME"]
    user = os.environ["IW_CORE_DB_USER"]
    password = os.environ["IW_CORE_DB_PASSWORD"]
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
```

**Rule**: The application MUST fail fast with a clear error if any required environment variable is missing. No silent fallbacks to hardcoded values.

### 8.4. Test Isolation

Tests do NOT use the compose files or `.env`. They use `testcontainers`,
which starts an independent PostgreSQL container on a random Docker-assigned
port:

```
Platform DB (production):  docker run raw docker   → port 5433  → container "postgres"
Platform DB (bootstrap):  docker-compose.bootstrap.yml → port 5433  → container "iw-ai-core-db"
Test session A:           testcontainers           → random port → container "testcontainers-postgres-xxxx"
Test session B:           testcontainers           → random port → container "testcontainers-postgres-yyyy"
```

No shared ports. No shared containers. No shared data. Tests can run while the platform is serving live batches.

**Tests MUST NOT load `.env`**. The test `conftest.py` explicitly does NOT call `load_dotenv()`. All DB configuration comes from the testcontainer.

---

## 9. Configuration

### 9.1. Platform Configuration

All platform configuration lives in `.env` (loaded via `python-dotenv`). See Section 8.1 for the full `.env.example` template.

**Configuration hierarchy:**
1. Environment variables (highest priority — override everything)
2. `.env` file in repo root (loaded by `python-dotenv`)
3. Defaults in `.env.example` documentation (for reference only — never used as actual fallbacks)

**Rule**: No hardcoded ports, URLs, paths, or credentials anywhere in the codebase. If a value can change between environments or machines, it MUST be in `.env`.

### 9.2. Project Configuration (`.iw-orch.json`)

Per-project settings are in each project's repo root. See `IW_AI_Core_Architecture.md` section 4.1 for the full schema.

### 9.3. Project Registry (`projects.toml`)

Central registry in the iw-ai-core repo root. Read by the daemon on startup and on SIGHUP.

---

## 10. Decisions Log

| # | Decision | Choice | Alternatives Considered | Rationale |
|---|----------|--------|------------------------|-----------|
| D1 | ORM mode | Sync SQLAlchemy | Async SQLAlchemy | Daemon is single-threaded polling. Async adds complexity for no benefit. |
| D2 | CLI framework | Click | argparse, Typer | Click is mature, well-documented, supports command groups natively. Typer adds a dependency on Click anyway. |
| D3 | CSS framework | Tailwind (CDN) | Custom CSS, Bootstrap | Clean utilities, no build step via CDN, consistent from day one. |
| D3a | Tailwind CLI fallback | Append plain CSS to `dashboard/static/styles.css` | Tailwind CLI, `make css` | CLI unreliable in agent worktrees due to incomplete `node_modules`; plain CSS is served as-is without compilation. |
| D4 | PostgreSQL driver | psycopg v3 | psycopg2 | Better typing, pure Python fallback, built-in pool. |
| D5 | Compression | zstandard | gzip, lz4 | Best balance of speed and ratio. 3-5x faster decompression than gzip. |
| D6 | Test containers | testcontainers | docker-compose.test.yml, SQLite | testcontainers provides complete isolation with random ports. SQLite doesn't support FOR UPDATE. docker-compose.test.yml requires port coordination. |
| D7 | Package manager | uv | pip, poetry | Fast, deterministic, modern. Same direction as InnoForge. |
| D8 | Charts | Chart.js (CDN) | D3.js, Plotly | Lightweight, no npm, good enough for analytics. |
| D9 | Dashboard tests | None (manual) | Playwright, Selenium | Internal tool, server-rendered. Cost of browser test maintenance outweighs value. |
| D10 | Bash script tests | None (manual) | bats, shunit2 | Scripts are ported from InnoForge and battle-tested. Low defect rate vs test maintenance cost. |
| D11 | Configuration | `.env` + python-dotenv | pydantic-settings, dynaconf | python-dotenv is minimal, no magic, explicit. Pydantic-settings adds unnecessary abstraction for a single-user tool. |
| D12 | No hardcoded ports | All via `.env` | Convention defaults | Prevents collisions, enables running multiple instances, tests never touch live services. |

---

## 11. Security Scanning

Three security axes are covered:

| Axis | Tool | CI Job | Local target | Gating |
|------|------|--------|--------------|--------|
| SAST / secrets | Bandit | `deps-audit` | `make security-deps` | HIGH/CRITICAL fails |
| Dependency audit | pip-audit | `deps-audit` | `make security-deps` | Any vuln fails `--strict` |
| IaC scanning | Trivy | `iac-scan` | `make security-iac` | HIGH/CRITICAL fails |

Developers can run `make security-deps security-iac` locally before committing. The CI workflow runs on every PR and push and is gated on HIGH/CRITICAL findings for Bandit and Trivy, and any vulnerability for pip-audit (with `--strict`).

Trivy image scanning is TODO pending a build step for versioned images in CI.
