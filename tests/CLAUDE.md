# tests/ — Test Suite

pytest-based tests with strict DB isolation rules.

## Structure

| Path | Purpose |
|------|---------|
| `conftest.py` | Root fixtures: `pg_engine`, `db_session`, `test_project` |
| `unit/` | Fast, no I/O — config, state machine, logic, CLI parsing |
| `integration/` | Real PostgreSQL via testcontainers — models, DB behavior, CLI e2e |
| `fixtures/` | Shared test data helpers |

## Testing Rules (NON-NEGOTIABLE)

1. **NEVER** connect to live DB (port 5433) — all DB tests use testcontainers on random ports
2. **NEVER** call `importlib.reload(orch.config)` — it re-runs `load_dotenv()` restoring deleted env vars from `.env`; use `monkeypatch.delenv()` only
3. **NEVER** mock the database in integration tests — `SELECT FOR UPDATE` locking can't be tested with mocks
4. **MUST** replace psycopg2 URL from testcontainers before use:
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
- Integration test fixtures are `scope="session"` for the container, `scope="function"` for DB transactions (rollback after each test)
- `test_project` fixture creates a `Project` row; tests that create work items must use this project's `id`
