# F-00072_S01_Backend_prompt

**Work Item**: F-00072 -- Pragmatic Migration Safety + Schema Validation
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures are exempt.)

## ⛔ Migrations: agents generate, daemon applies

**CRITICAL**: this step writes a TEST around migrations. It MUST NOT
add an alembic migration, run `alembic upgrade` against the live DB,
or run `make db-migrate`. The test itself drives alembic against a
testcontainer ONLY.

## Input Files

- `uv run iw item-status F-00072 --json`
- `ai-dev/active/F-00072/F-00072_Feature_Design.md`
- `tests/conftest.py` — pg_engine fixture pattern
- `tests/CLAUDE.md` — strict live-DB-guard rules
- `tests/integration/test_migration_pipeline.py` — pattern for testcontainer + alembic interaction
- `orch/db/migrations/env.py` — alembic env config
- `alembic.ini`
- `docker-compose.bootstrap.yml` — production Postgres version
- `.github/workflows/compliance-scan.yml` — pattern for SHA pinning + permissions

## Output Files

- New: `tests/integration/test_migration_roundtrip.py`
- New: `.github/workflows/schema-validation.yml`
- Modified: `docs/IW_AI_Core_Daemon_Design.md` or `tests/CLAUDE.md` (≤80-word note)
- `ai-dev/active/F-00072/reports/F-00072_S01_Backend_report.md`

## Context

Implement the generic migration roundtrip test and the alembic-check CI workflow.

## Requirements

### 1. Generic roundtrip test

`tests/integration/test_migration_roundtrip.py`:

**Established pattern**: follow `tests/integration/test_iw_core_instance_migration.py` — it uses a module-scoped `PostgresContainer`, the `alembic.command` Python API (not subprocess), and `pytest.MonkeyPatch.context()` to set `IW_CORE_DB_*` env vars. Replicate that pattern here.

```python
"""Latest-3 migration roundtrip test — F-00072.

For each of the last 3 revisions (oldest → newest):
  downgrade base          — reset to empty (ensures clean state per parametrized case)
  upgrade <rev>           — apply up to this revision
  downgrade <parent_rev>  — step back one via EXPLICIT parent revision ID (rule 4a)
  upgrade head            — restore to head

Asserts each alembic.command call completes without raising.
After the final upgrade head, verifies the schema contains all Base.metadata tables.

Test reads alembic history at collection time — adding a new revision auto-shifts
the window with no edits to this file.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from testcontainers.postgres import PostgresContainer

from orch.db.models import Base

REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _ordered_revisions() -> list[str]:
    """Return revision IDs topologically, oldest first."""
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    script = ScriptDirectory.from_config(cfg)
    revs = list(script.walk_revisions(base="base", head="heads"))
    revs.reverse()  # oldest → newest
    return [rev.revision for rev in revs]


def _latest_n(n: int = 3) -> list[str]:
    revs = _ordered_revisions()
    return revs[-n:] if len(revs) >= n else revs


def _parent_rev(revision: str) -> str | None:
    """Look up the explicit parent revision ID (rule 4a: never use -1)."""
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    script = ScriptDirectory.from_config(cfg)
    rev_obj = script.get_revision(revision)
    parent = rev_obj.down_revision if rev_obj else None
    # down_revision may be a tuple for merge revisions — take first
    if isinstance(parent, tuple):
        parent = parent[0]
    return parent  # None means base (no parent)


# Module-scoped container — one spin-up for all parametrized cases.
# (Mirroring test_iw_core_instance_migration.py pattern.)
@pytest.fixture(scope="module")
def _roundtrip_pg():
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def _roundtrip_db_url(_roundtrip_pg: PostgresContainer) -> str:
    return _roundtrip_pg.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )


@pytest.mark.integration
@pytest.mark.parametrize("revision", _latest_n(3), ids=lambda r: r[:8])
def test_migration_roundtrip(revision: str, _roundtrip_db_url: str) -> None:
    """For each of the latest 3 revs: reset → upgrade(rev) → downgrade(parent) → upgrade head."""
    db_url = _roundtrip_db_url
    parsed = urlparse(db_url.replace("postgresql+psycopg://", "postgresql://"))

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("IW_CORE_DB_HOST", str(parsed.hostname))
        mp.setenv("IW_CORE_DB_PORT", str(parsed.port))
        mp.setenv("IW_CORE_DB_NAME", parsed.path.lstrip("/"))
        mp.setenv("IW_CORE_DB_USER", str(parsed.username))
        mp.setenv("IW_CORE_DB_PASSWORD", str(parsed.password))

        alembic_cfg = _alembic_cfg(db_url)

        # 1. Reset to empty — ensures clean state regardless of prior test's final state
        command.downgrade(alembic_cfg, "base")

        # 2. Upgrade to target revision
        command.upgrade(alembic_cfg, revision)

        # 3. Downgrade to explicit parent (rule 4a: never use -1)
        parent = _parent_rev(revision)
        if parent is not None:
            command.downgrade(alembic_cfg, parent)
        # else: base revision has no parent; skip downgrade step

        # 4. Restore to head
        command.upgrade(alembic_cfg, "head")

    # 5. Verify final schema has all expected tables
    engine = create_engine(db_url, pool_pre_ping=True)
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    actual_tables.discard("alembic_version")
    expected_tables = set(Base.metadata.tables.keys())
    missing = expected_tables - actual_tables
    assert not missing, (
        f"After upgrade head, missing tables: {missing} (revision under test: {revision[:8]})"
    )
    engine.dispose()
```

**Critical requirements enforced by the above skeleton**:
- Uses `alembic.command` Python API (not subprocess) — per established pattern in `test_iw_core_instance_migration.py`.
- Uses explicit parent revision ID for downgrade (**rule 4a** from `tests/CLAUDE.md`: "never `-1`").
- Uses `pytest.MonkeyPatch.context()` to set `IW_CORE_DB_*` — does NOT use `importlib.reload(orch.config)`.
- Uses module-scoped `PostgresContainer` (one spin-up, state reset via `downgrade base` per parametrized case).
- Uses `postgresql+psycopg://` URL (not psycopg2).
- Does NOT use the shared session-scoped `db_engine` from integration/conftest.py (which runs `Base.metadata.create_all()`, bypassing alembic, making the container state incompatible).

**Before writing the test**: read `orch/db/migrations/env.py` to verify how the DB URL is resolved (env vars vs `orch.config.get_db_url()`). The `MonkeyPatch.context()` env var override covers both cases as long as env.py reads `IW_CORE_DB_*` from the environment (not from a cached config object). Adjust if needed.

**Verify that `_latest_n` returns revisions at collection time**: the `_latest_n(3)` call at module level runs during pytest collection. Ensure `alembic.ini` / `orch/db/migrations/` is accessible from the working directory (it is, since `REPO_ROOT` is the project root).

### 2. Schema validation workflow

`.github/workflows/schema-validation.yml`:

```yaml
# Schema validation — runs `alembic check` on every PR to catch
# model/migration drift (a model field added without a migration).
#
# Action versions are pinned to commit SHAs.

name: Schema Validation

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  alembic-check:
    name: alembic check
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:<MAJOR>     # match docker-compose.bootstrap.yml
        env:
          POSTGRES_USER: iw
          POSTGRES_PASSWORD: iw
          POSTGRES_DB: iw_ai_core
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U iw"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10

    env:
      IW_CORE_DB_HOST: localhost
      IW_CORE_DB_PORT: "5432"
      IW_CORE_DB_NAME: iw_ai_core
      IW_CORE_DB_USER: iw
      IW_CORE_DB_PASSWORD: iw

    steps:
      - name: Checkout
        uses: actions/checkout@<PIN>          # pin to 40-char SHA
        with:
          persist-credentials: false

      - name: Install uv
        uses: astral-sh/setup-uv@<PIN>

      - name: Install deps
        run: uv sync --frozen

      - name: Apply migrations
        run: uv run alembic upgrade head

      - name: Check for drift
        run: uv run alembic check
```

Resolve `<PIN>` placeholders using the same approach as `compliance-scan.yml`. Resolve `<MAJOR>` by reading the postgres image in `docker-compose.bootstrap.yml` (likely `postgres:16` or similar).

### 3. Documentation note

Append to either `docs/IW_AI_Core_Daemon_Design.md` (preferred — it discusses migrations) or `tests/CLAUDE.md`:

```markdown
### Migration safety net

`tests/integration/test_migration_roundtrip.py` runs an upgrade/downgrade/upgrade cycle for the **latest 3** alembic revisions on each test run. The window is dynamic — adding a new migration auto-shifts it without code edits.

`alembic check` runs on every PR via `.github/workflows/schema-validation.yml` to catch drift between model definitions and migrations.

Older revisions are not roundtripped on every PR (pragmatic choice — they were verified at the time via the daemon's pre-merge dry-run).
```

≤80 words.

### 4. Out of scope

- No new alembic revision.
- No edits to `alembic.ini` or `env.py` unless absolutely required to make the test work; if changes are needed, document and flag in the report.
- No live-DB connections.

## Project Conventions

- Read `CLAUDE.md`, `tests/CLAUDE.md`, `docs/IW_AI_Core_Agent_Constraints.md`.
- Use `psycopg` (not `psycopg2`) per CLAUDE.md.
- Match the testcontainer fixture pattern in `tests/conftest.py`.
- SHA-pin all GitHub action versions.

## TDD Requirement

Demonstrate RED for the test by introducing a deliberate downgrade bug in a NEW temporary file (do NOT modify the real migrations), confirm the test fails with the revision in the message, then revert.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`
5. `make test-integration` — passes including the new test

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00072",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_migration_roundtrip.py",
    ".github/workflows/schema-validation.yml",
    "docs/IW_AI_Core_Daemon_Design.md or tests/CLAUDE.md"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "action_pins_resolved": [],
  "blockers": [],
  "notes": ""
}
```
