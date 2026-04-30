# F-00072 S01 Backend Report

## What was done

Implemented the generic migration roundtrip test (`tests/integration/test_migration_roundtrip.py`) and the `alembic check` CI workflow (`.github/workflows/schema-validation.yml`). Added a migration safety net note to `docs/IW_AI_Core_Daemon_Design.md`.

### Files changed

- `tests/integration/test_migration_roundtrip.py` — new file
- `.github/workflows/schema-validation.yml` — new file
- `docs/IW_AI_Core_Daemon_Design.md` — added migration safety net note (~60 words)

### Schema validation workflow

Uses SHA-pinned `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5` and `astral-sh/setup-uv@0880764`. PostgreSQL service image matches `docker-compose.bootstrap.yml` (`postgres:15`). Applies migrations then runs `alembic check` to catch model/migration drift on every PR.

### Roundtrip test design

- Module-scoped `PostgresContainer` (one spin-up for all 3 parametrized cases)
- `pytest.MonkeyPatch.context()` sets `IW_CORE_DB_*` env vars inside the test body
- Uses explicit parent revision ID for downgrade (rule 4a from `tests/CLAUDE.md`: never `-1`)
- State reset via `downgrade base` per parametrized case ensures isolation
- After final `upgrade head`, verifies all `Base.metadata.tables` are present

## Test results

```
tests/integration/test_migration_roundtrip.py::test_migration_roundtrip[bd4ed52c] PASSED
tests/integration/test_migration_roundtrip.py::test_migration_roundtrip[fdf63560] PASSED
tests/integration/test_migration_roundtrip.py::test_migration_roundtrip[add_diag] PASSED
```

Full integration suite: 1157 passed, 4 failed (pre-existing failures in `test_baseline_qv_pipeline.py`, `test_compose_split.py`, `test_project_docs.py` — unrelated to migration changes).

## Issues and observations

- `make format` required running `ruff format` on the new test file before checks passed
- Pre-existing unit test failures in RAG diagram generation tests (9 failures) are unrelated to this work
- Pre-existing lint `ARG001` unused argument warnings in `dashboard/routers/code_qa.py:70` are pre-existing
- Pre-existing typecheck errors in `orch/daemon/container_info.py` (4 errors) are pre-existing
- No changes to `alembic.ini`, `env.py`, or migration files were required

## Action pins resolved

- `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5` (from `compliance-scan.yml`)
- `astral-sh/setup-uv@0880764` (from GitHub release v8.1.0)
- PostgreSQL service `image: postgres:15` (matches `docker-compose.bootstrap.yml`)