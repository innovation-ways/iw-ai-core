# tests/ — Test Suite

pytest-based tests with strict DB isolation rules.

## Required reading (agents writing or reviewing tests)

- **`skills/iw-ai-core-testing/SKILL.md` — MUST read before writing, reviewing, or designing any test.** Assertion-strength rules, the live-DB-guard / testcontainer rules, cross-project isolation, state-machine/property guidance, the test red-flag checklist.
- **`docs/IW_AI_Core_Testing_Strategy.md`** — the full strategy: layers, infrastructure, conventions, quality gates, known gaps, roadmap.
- **`ai-dev/work/TESTS_ENHANCEMENT.md`** — the phased plan for improving testing here (status of each item).

## TDD & test quality (NON-NEGOTIABLE)

- **TDD = RED → GREEN → REFACTOR.** `backend-impl` writes the failing test first, *runs it and confirms it fails for the right reason*, records the RED output in its execution report, then writes the minimal implementation, then refactors with tests green. Tests are written *before* the implementation — not after, not alongside.
- **Coverage is a floor on what's exercised, not the gate.** A high coverage number with weak assertions is the failure mode, not the goal. Coverage has a `fail_under` floor (`pyproject.toml`); never drop it — but passing it is necessary, not sufficient. Every assertion must be one that would fail if the production code regressed (the "mutation test question" in the testing skill §0).
- **Every test must be able to fail.** If deleting the production line it covers wouldn't fail the test, the test is worthless — strengthen or remove it. Tests assert on *behaviour*, never only on their own mocks.

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
- E2E browser-verification fixtures live under `ai-dev/{active,archive}/<item>/e2e_fixtures/*.py` (loaded by `scripts/e2e_seed.py`, NOT pytest). The regression net is `tests/integration/test_e2e_seed.py` — when you add a new fixture or a new model with cross-mapper FKs, run `pytest tests/integration/test_e2e_seed.py` before merging. See the docstring in `scripts/e2e_seed.py` for the parent/child insert-order gotcha.

## Per-worktree DB vs testcontainers (F-00062)

Feature F-00062 introduces a per-worktree Postgres container for app runtime
(started by the daemon when the project ships `ai-dev/iw-config/`).
This is separate from `make test-integration`'s testcontainers.

- `make test-integration` **MUST** continue to use testcontainers (existing rule).
- The per-worktree DB is for the agent's app runtime (e.g., dashboard exercising
  Backend step changes), NOT for tests.
- Tests must NEVER assume the per-worktree DB exists — they spin up their own
  testcontainer.

## pytest-randomly — test-order randomisation

`pytest-randomly` is installed as a dev dependency but is **currently OFF by default**
via `-p no:randomly` in `pyproject.toml` `[tool.pytest.ini_options] addopts` — the
design's explicit fallback (CR-00048 AC1 / Desired Behavior). S01's bounded unit-suite
sweep was green, but `make diff-coverage` (which runs `tests/integration/` +
`tests/dashboard/` together under a fresh `pytest` invocation) surfaced order-dependent
fixture failures across ~50 integration tests that 5 fix cycles could not converge.
Follow-up `P1-CR-C-followup-randomly` tracks the cleanup that re-enables randomisation
by default.

**Opt in manually** (for the follow-up cleanup, or to surface order-dependence
ad-hoc):

```bash
# Re-enable randomisation (overrides `-p no:randomly` from addopts)
uv run pytest tests/unit/ -p randomly -q

# Reproduce a specific seed
uv run pytest tests/unit/ -p randomly --randomly-seed=<N> -q

# Surface order-dependence across multiple seeds (the bounded-sweep recipe)
uv run pytest tests/unit/ -p randomly --randomly-seed=12345 -q
uv run pytest tests/unit/ -p randomly --randomly-seed=67890 -q
uv run pytest tests/unit/ -p randomly --randomly-seed=11111 -q
```

When randomisation is active, the per-run seed is printed at the top:

```
Using --randomly-seed=770868803
```

**If a test fails under random order but passes in fixed order**, it is
**order-dependent** — a test isolation bug (state leaking between tests).
Fix the leaking side effect (or quarantine it with `@pytest.mark.order_dependent`
+ a tracking comment). A quarantined test must still pass when it runs under
random order; if it genuinely cannot, mark it `@pytest.mark.xfail(strict=False, ...)`
as well.

**Cleanup contract** (for the follow-up): integration-suite order-dependence must
be eliminated (or every offender registered with `@pytest.mark.order_dependent`)
before `-p no:randomly` is removed from `addopts`. Until then, randomisation is
opt-in only.

## Smoke layer SLA (CR-00052, P1-CR-E)

`make smoke` runs the curated `@pytest.mark.smoke` set. **Contract:**

- **<=15 tests** total (count by `grep -rc "@pytest.mark.smoke" tests/`).
- **<60 s** wall-clock on a clean dev environment (measured 2026-05-14: ~13s).
- **Covers 5 critical paths**: daemon-worktree-start, dashboard-main-pages, iw-next-id, work-item-queue, /healthz.

Each path has >=1 smoke test mapped to it (audit table in CR-00052's S01 report). Adding a new `@pytest.mark.smoke` decorator requires:

1. Identifying which critical path it covers (or adding a new path to the contract and updating this doc).
2. Re-auditing the count — if it would push the total over 15, **remove** a redundant existing decorator or **don't add** the new one.
3. Re-measuring wall-clock — if it would push over 60 s, profile and trim.

The contract is currently **prose-enforced** — no `make smoke-sla` command. A future follow-up may add mechanical enforcement if drift happens (see TESTS_ENHANCEMENT.md §5 / P1-CR-E-followup-sla-enforcement, not yet filed).
