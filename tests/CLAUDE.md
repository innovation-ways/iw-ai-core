# tests/ — Test Suite

pytest-based tests with strict DB isolation rules.

## Structure

| Path | Purpose |
|------|---------|
| `conftest.py` | Root fixtures: `pg_engine`, `db_session`, `test_project` |
| `unit/` | Fast, no I/O — config, state machine, logic, CLI parsing |
| `integration/` | Real PostgreSQL via testcontainers — models, DB behavior, CLI e2e |
| `dashboard/` | FastAPI TestClient tests — chat a11y/security/templates, code layout/SSE wiring, project onboarding |
| `fixtures/` | Shared test data helpers |

## Testing Rules (NON-NEGOTIABLE)

1. **NEVER** connect to live DB (port 5433) — all DB tests use testcontainers on random ports
2. **NEVER** call `importlib.reload(orch.config)` — it re-runs `load_dotenv()` restoring deleted env vars from `.env`; use `monkeypatch.delenv()` only
3. **NEVER** mock the database in integration tests — `SELECT FOR UPDATE` locking can't be tested with mocks
4. **NEVER** run raw `docker` / `docker compose` / `docker-compose` from test code. The ONLY allowed docker usage in tests is via `testcontainers` fixtures (which self-label under Ryuk and self-destruct). Never stop/remove containers from test teardown — let the fixture lifecycle handle it. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.
4a. **NEVER** invoke `alembic` directly from test code outside of dedicated migration-round-trip tests. In those tests, downgrade to a *specific revision ID*, never `-1`, so the test stays stable as new migrations land on top. Migrations are daemon-driven in production — agents generate, daemon applies. See `docs/IW_AI_Core_Agent_Constraints.md`.
5. **MUST** replace psycopg2 URL from testcontainers before use:
   ```python
   url = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
   ```
5. **MUST** run FTS DDL after `Base.metadata.create_all()` — the trigger is raw SQL not captured by SQLAlchemy:
   ```python
   from orch.db.models import FTS_FUNCTION_SQL, FTS_TRIGGER_SQL
   with engine.connect() as conn:
       conn.execute(text(FTS_FUNCTION_SQL))
       conn.execute(text(FTS_TRIGGER_SQL))
       conn.commit()
   ```

## testcontainers Pattern

```python
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def pg_engine():
    with PostgresContainer("postgres:15") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        engine = create_engine(url)
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(text(FTS_FUNCTION_SQL))
            conn.execute(text(FTS_TRIGGER_SQL))
            conn.commit()
        yield engine
```

## Running Tests

```bash
make test-unit                              # Fast, no containers
make test-integration                       # Starts PostgreSQL testcontainer (~3s)
make quality                                # ruff check + ruff format --check + mypy
make check                                  # quality + all tests

uv run pytest tests/unit/test_config.py -v
uv run pytest tests/integration/test_models.py -v
uv run pytest -k "test_next_id" -v         # Match by test name
```

## Gotchas

- Unit tests must not import `orch.config` at module level if env vars are being patched — import inside the test function or use `importlib` carefully
- **NEVER import `dashboard.routers.*` or `dashboard.dependencies` in a unit test unless a testcontainer `db_session` is in scope.** These modules load `SessionLocal` on import via `orch.db.session.__getattr__`, which calls `safe_create_engine()`. The live-DB guard fires immediately because `tests/conftest.py` redirects `IW_CORE_DB_HOST:PORT` to a blocked address — making any engine URL look like the "live" DB to `is_live_db_url()`. You will see `LiveDbConnectionRefusedError` at *collection time*, before any test body runs, and every test in the file will fail. To unit-test a pure function from a router module (e.g. `_preprocess_mermaid`): either (a) extract it to a utility module with no DB in its import chain, or (b) use the testcontainer-backed `db_session` fixture + `app.dependency_overrides[get_db]` pattern shown in `tests/dashboard/test_jobs_filter_ui.py`.
- Integration test fixtures are `scope="session"` for the container, `scope="function"` for DB transactions (rollback after each test)
- `test_project` fixture creates a `Project` row; tests that create work items must use this project's `id`

## Per-worktree DB vs testcontainers (F-00062)

Feature F-00062 introduces a per-worktree Postgres container for app runtime
(started by the daemon when the project ships `ai-dev/iw-config/`).
This is separate from `make test-integration`'s testcontainers.

- `make test-integration` **MUST** continue to use testcontainers (existing rule).
- The per-worktree DB is for the agent's app runtime (e.g., dashboard exercising
  Backend step changes), NOT for tests.
- Tests must NEVER assume the per-worktree DB exists — they spin up their own
  testcontainer.
